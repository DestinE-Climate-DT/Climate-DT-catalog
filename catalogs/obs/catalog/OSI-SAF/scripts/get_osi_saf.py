#!/usr/bin/env python3
"""
osi_ice_conc.py — download OSI SAF sea-ice concentration files (any
product version) and concatenate them into yearly netCDF files with cdo.

Combines two former shell scripts:
  1. Crawl a THREDDS catalog for a hemisphere/year/month, build URL
     lists, and download the matching files (like the old download.sh).
  2. Use `cdo cat` to merge all daily files for each year into a single
     per-year netCDF file (like the old concat.sh).

Product mapping
----------------
PRODUCTS below maps a short product key (e.g. "438", "450a", "458") to
its THREDDS catalog base URL and the version tag used in its filenames
(e.g. "ice_conc_nh_ease2-250_<version>_<date>.nc"). Fill in the catalog
URLs for the products you need — "438" is provided as a working example.

Output layout
-------------
Downloads go to:   <outdir>/<product>/daily/<year>/<month>/<file>.nc
Yearly merges go to: <outdir>/<product>/<file>_<year>.nc

Usage
-----
Do both (download, then concatenate) — the default when neither
--download nor --concat is given:
    ./osi_ice_conc.py nh --product 438 --start-year 2021 --end-year 2025 --outdir ./osi

Download only:
    ./osi_ice_conc.py nh --product 450a --download --start-year 2021 --end-year 2025 --outdir ./osi

Concatenate only (reads .nc files from <outdir>/<product>/daily, recursively):
    ./osi_ice_conc.py nh --product 438 --concat --start-year 1979 --end-year 2020 --outdir ./osi

Notes
-----
* `cdo` must be installed and on PATH for the concat step (this script
  shells out to it, same as the original `cdo cat ...` calls).
* Downloads are resumable (like `wget -c`): partially downloaded files
  are continued via HTTP Range requests.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import requests

# --------------------------------------------------------------------------
# Product mapping — add your own catalog URLs / version tags here.
# --------------------------------------------------------------------------
PRODUCTS = {
    "438": {
        "catalog": "https://thredds.met.no/thredds/catalog/osisaf/met.no/reprocessed/ice/conc_438_files",
        "version": "cdr-v3p0",
    },
    "450a1": {
        "catalog": "https://thredds.met.no/thredds/catalog/osisaf/met.no/reprocessed/ice/conc_450a1_files",  # TODO: fill in the THREDDS catalog base URL for osi-450a
        "version": "cdr-v3p1",  # TODO: filename version tag, e.g. "icdr-v3p0"
    },
    "458": {
        "catalog": "https://thredds.met.no/thredds/catalog/osisaf/met.no/reprocessed/ice/conc_amsr_458_files",  # TODO: fill in the THREDDS catalog base URL for osi-458
        "version": "cdr-v3p0",  # TODO: filename version tag
    },
}

BASE_FS = "https://thredds.met.no/thredds/fileServer"

URLPATH_RE = re.compile(r'urlPath="([^"]+)"')
DATE8_RE = re.compile(r"(\d{8})")  # first yyyymmdd-like run of 8 digits in a filename


# --------------------------------------------------------------------------
# Step 1: build URL lists by crawling the THREDDS catalog
# --------------------------------------------------------------------------
def build_url_lists(hemi: str, catalog_base: str, start_year: int, end_year: int,
                     url_list_dir: Path) -> list[Path]:
    url_list_dir.mkdir(parents=True, exist_ok=True)
    list_files: list[Path] = []

    for year in range(start_year, end_year + 1):
        list_file = url_list_dir / f"{hemi}_{year}.txt"
        urls: list[str] = []

        for month in range(1, 13):
            m = f"{month:02d}"
            cat_url = f"{catalog_base}/{year}/{m}/catalog.xml"
            print(f"Indexing {year}-{m}")
            try:
                resp = requests.get(cat_url, timeout=30)
                resp.raise_for_status()
            except requests.RequestException:
                # Mirror the shell script's `|| continue` on missing/failed catalogs
                continue

            for match in URLPATH_RE.finditer(resp.text):
                url_path = match.group(1)
                if f"ice_conc_{hemi}_" in url_path:
                    urls.append(f"{BASE_FS}/{url_path}")

        list_file.write_text("\n".join(urls) + ("\n" if urls else ""))
        list_files.append(list_file)

    return list_files


# --------------------------------------------------------------------------
# Step 2: download files from the URL lists (resumable, like wget -c)
# --------------------------------------------------------------------------
def dest_subdir_for(filename: str, product_dir: Path) -> Path:
    """<product_dir>/daily/<year>/<month>, parsed from the yyyymmdd... in the filename."""
    match = DATE8_RE.search(filename)
    if match:
        yyyymmdd = match.group(1)
        return product_dir / "daily"
    return product_dir / "daily" / "unknown"


def download_file(url: str, dest_dir: Path, tries: int = 3, timeout: int = 30,
                   waitretry: float = 5.0) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    dest = dest_dir / filename

    for attempt in range(1, tries + 1):
        try:
            headers = {}
            mode = "wb"
            existing = dest.stat().st_size if dest.exists() else 0
            if existing:
                headers["Range"] = f"bytes={existing}-"
                mode = "ab"

            with requests.get(url, headers=headers, stream=True, timeout=timeout) as resp:
                if resp.status_code == 416:
                    # Already fully downloaded
                    return
                resp.raise_for_status()
                with open(dest, mode) as f:
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        if chunk:
                            f.write(chunk)
            return  # success
        except requests.RequestException as exc:
            print(f"  attempt {attempt}/{tries} failed for {filename}: {exc}")
            if attempt < tries:
                time.sleep(waitretry)
    print(f"  giving up on {filename}")


def download_from_lists(list_files: list[Path], product_dir: Path) -> None:
    for list_file in list_files:
        print(f"Downloading from {list_file}")
        urls = [line.strip() for line in list_file.read_text().splitlines() if line.strip()]
        for url in urls:
            filename = url.rsplit("/", 1)[-1]
            dest_dir = dest_subdir_for(filename, product_dir)
            download_file(url, dest_dir)


# --------------------------------------------------------------------------
# Step 3: concatenate per-year files with cdo cat
# --------------------------------------------------------------------------
def concat_years(hemi: str, start_year: int, end_year: int, product_dir: Path, version: str) -> None:
    daily_dir = product_dir / "daily"
    product_dir.mkdir(parents=True, exist_ok=True)

    for year in range(start_year, end_year + 1):
        print(f"Processing year {year} for hemisphere {hemi}...")

        pattern = f"ice*_{year}????1200.nc"
        matches = sorted(daily_dir.rglob(pattern))
        if not matches:
            print(f"  no files matching {pattern} under {daily_dir}, skipping")
            continue

        outfile = product_dir / f"ice_conc_{hemi}_ease2-250_{version}_{year}.nc"
        cmd = ["cdo", "-f", "nc4", "-z", "zip", "cat", *[str(p) for p in matches], str(outfile)]
        subprocess.run(cmd, check=True)

        print(f" -> Created {outfile}")

    print("All years processed.")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("hemisphere", choices=["nh", "sh"], help="Hemisphere")
    parser.add_argument("--product", choices=sorted(PRODUCTS), default="438",
                         help="OSI SAF product version (see PRODUCTS mapping in the script)")
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--outdir", type=Path, default=Path("osi-saf"),
                         help="Root output directory; files are organized under "
                              "<outdir>/<product>/daily/<year>/<month>/")
    parser.add_argument("--download", action="store_true", help="Only download files")
    parser.add_argument("--concat", action="store_true", help="Only concatenate files with cdo")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    hemi = args.hemisphere
    product = PRODUCTS[args.product]

    if not product["catalog"]:
        sys.exit(f"error: no catalog URL configured for product '{args.product}' — "
                  f"fill it in the PRODUCTS mapping at the top of this script.")

    product_dir = args.outdir / f"osi-{args.product}-{product['version']}-{hemi}"

    # Default to doing both when neither flag is given
    do_download = args.download or not (args.download or args.concat)
    do_concat = args.concat or not (args.download or args.concat)

    if do_download:
        list_files = build_url_lists(hemi, product["catalog"], args.start_year, args.end_year,
                                      product_dir / "url_lists")
        download_from_lists(list_files, product_dir)
        print(f"Done downloading. Files saved under: {product_dir}/daily/")

    if do_concat:
        if not product["version"]:
            sys.exit(f"error: no version tag configured for product '{args.product}' — "
                      f"fill it in the PRODUCTS mapping at the top of this script.")
        concat_years(hemi, args.start_year, args.end_year, product_dir, product["version"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
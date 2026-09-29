#!/usr/bin/env python3
"""Download CERES/C3S SST data from CDS month-by-month and package into
compressed yearly NetCDF4 files."""
import argparse
import glob
import os
import subprocess
import zipfile
import cdsapi
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATASET = "satellite-sea-surface-temperature"
MONTHS = [f"{m:02d}" for m in range(1, 13)]
DAYS = [f"{d:02d}" for d in range(1, 32)]
# Variables to extract as separate monthly-mean files during post-processing
VARIABLES = ["analysed_sst", "sea_ice_fraction"]

def parse_args():
    p = argparse.ArgumentParser(
        description="Download CERES/C3S SST data from CDS month-by-month and "
        "package into compressed yearly NetCDF4 files."
    )
    p.add_argument("--start", type=int, required=True, help="First year to download (e.g., 2020)")
    p.add_argument("--end", type=int, required=True, help="Last year to download (e.g., 2024)")
    p.add_argument("--output-dir", type=str, default="./sst_data", help="Target output directory")
    return p.parse_args()


def build_request(year: str, month: str) -> dict:
    return {
        "variable": "all",
        "processinglevel": "level_4",
        "sensor_on_satellite": "combined_product",
        "version": "3_0",
        "temporal_resolution": "daily",
        "year": [year],
        "month": [month],
        "day": DAYS,
    }


def unzip_if_needed(filepath: str):
    """CDS sometimes delivers a .nc-named file that's actually a zip archive
    containing one .nc per day. Detect, extract, and merge into a single
    monthly file at the same path (in-place, using cdo)."""
    if not zipfile.is_zipfile(filepath):
        return

    extract_dir = filepath + "_extracted"
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(filepath) as zf:
        names = [n for n in zf.namelist() if n.endswith(".nc")]
        zf.extractall(extract_dir, members=names)

    daily_files = sorted(os.path.join(extract_dir, n) for n in names)
    os.remove(filepath)

    if len(daily_files) == 1:
        os.replace(daily_files[0], filepath)
    else:
        cdo_cmd = ["cdo", "-f", "nc4", "cat", *daily_files, filepath.replace(".zip", ".nc")]
        result = subprocess.run(cdo_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"cdo failed merging daily files for {filepath}:\n{result.stderr}")

    for f in daily_files:
        if os.path.exists(f):
            os.remove(f)
    os.rmdir(extract_dir)


def download_year(client: cdsapi.Client, year: int, temp_dir: str) -> bool:
    """Download all months for a year. Returns True if all 12 succeeded."""
    year_str = str(year)
    os.makedirs(temp_dir, exist_ok=True)

    for month in MONTHS:
        monthly_file = os.path.join(temp_dir, f"sst_{year_str}_{month}.zip")
        logger.info(f" Fetching data for {year_str}-{month}...")
        if os.path.exists(monthly_file):
            logger.info(f" Month {month} already downloaded, skipping...")
        else:
            try:
                client.retrieve(DATASET, build_request(year_str, month), monthly_file)
            except Exception as e:
                        logger.error(f" [ERROR] Failed to download {year_str}-{month}: {e}")
                        return False
        logger.info(f" Unzipping and merging {year_str}-{month}...")
        try:
            unzip_if_needed(monthly_file)
        except Exception as e:
            logger.error(f" [ERROR] Failed to unzip {year_str}-{month}: {e}")
            return False

    downloaded = sorted(glob.glob(os.path.join(temp_dir, "sst_*.nc")))
    return len(downloaded) == 12



def package_year(temp_dir: str, output_dir: str, year: int, variables=VARIABLES) -> bool:
    """Merge monthly files for the year, then compute monthly means per
    variable into variable-specific subfolders via CDO."""
    logger.info(f"Processing year {year}")
 
    files = sorted(glob.glob(os.path.join(str(temp_dir), f"sst_{year}_*.nc")))
    if len(files) != 12:
        logger.warning(f"Expected 12 monthly files for {year}, found {len(files)}, skipping")
        return False
 
    # Skip entirely if every variable's output already exists
    all_exist = all(
        os.path.exists(os.path.join(output_dir, var, f"sst_monthly_{year}_{var}.nc"))
        for var in variables
    )
    if all_exist:
        logger.info(f"All target files for {year} already exist, skipping processing")
        return True
 
    temp_merged = os.path.join(str(temp_dir), f"temp_merged_{year}.nc")
    try:
        if os.path.exists(temp_merged):
            os.remove(temp_merged)
            logger.info(f"Removed existing temporary file: {temp_merged}")
 
        logger.info(f"Merging monthly files for {year}...")
        merge_cmd = ["cdo", "mergetime", *files, temp_merged]
        result = subprocess.run(merge_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"CDO merge failed for {year}: {result.stderr}")
            return False
 
        success = True
        for var in variables:
            var_dir = os.path.join(str(output_dir), var)
            os.makedirs(var_dir, exist_ok=True)
            var_output_file = os.path.join(var_dir, f"ESA-CCI-L4_v3.0.1_monthly_{year}_{var}.nc")
 
            if os.path.exists(var_output_file):
                logger.info(f"Target file already exists, skipping: {var_output_file}")
                continue
 
            logger.info(f"Calculating monthly averages for {year}, variable: {var}...")
            monthly_cmd = [
                "cdo", "-f", "nc4", "-z", "zip",
                "settime,00:00:00", "-setday,1", "-monmean", f"-selname,{var}",
                temp_merged, var_output_file,
            ]
            result = subprocess.run(monthly_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"CDO monthly average failed for {year}, variable {var}: {result.stderr}")
                success = False
                continue
            logger.info(f"Created monthly averages file: {var_output_file}")

            logger.info("Producing r360x180 version...")
            r360x180_file = os.path.join(var_dir, f"ESA-CCI-L4_v3.0.1_monthly_{year}_{var}_r360x180.nc")
            remap_cmd = [
                "cdo", "-f", "nc4", "-z", "zip",
                "remapcon,r360x180", var_output_file, r360x180_file
            ]
            result = subprocess.run(remap_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"CDO remap failed for {year}, variable {var}: {result.stderr}")
                success = False
                continue
            logger.info(f"Created remapped file: {r360x180_file}")
 
        return success
    except Exception as e:
        logger.error(f"Error processing {year}: {e}")
        return False
    finally:
        if os.path.exists(temp_merged):
            os.remove(temp_merged)


def process_year(client: cdsapi.Client, year: int, output_dir: str):
    year_str = str(year)
    yearly_output_file = os.path.join(str(output_dir), f"sst_global_{year_str}.nc")

    if os.path.exists(yearly_output_file):
        logger.info(f"--> Year {year_str} already packaged ({yearly_output_file}). Skipping...")
        return

    logger.info(f"\n==========================================")
    logger.info(f" Processing Year: {year_str}")
    logger.info(f"==========================================")

    temp_dir = os.path.join(str(output_dir), f"temp_{year_str}")
    download_year(client, year, temp_dir)
    package_year(temp_dir, str(output_dir), year, VARIABLES)


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    client = cdsapi.Client()

    for year in range(args.start, args.end + 1):
        process_year(client, year, args.output_dir)

    logger.info("\nProcessing finished!")


if __name__ == "__main__":
    main()
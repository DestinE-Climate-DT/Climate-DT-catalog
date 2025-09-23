#!/usr/bin/env python3
"""
retrieve_esacci.py + postprocessing

Downloads daily .nc files from CEDA server and optionally performs post-processing:
 - yearly files of monthly averages using CDO
 - NC4 format with compression
 - timestamps fixed at midnight of first day of each month

Usage:
    python retrieve_esacci.py --start 2013-01-01 --end 2013-12-31 --out ./data --postproc

"""

import argparse
import os
import sys
import time
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter, Retry

# For postprocessing
import subprocess

# --- BASE CONFIGURATION ---
BASE_URL = "https://dap.ceda.ac.uk/neodc/eocis/data/global_and_regional/sea_surface_temperature/CDR_v3/Analysis/L4/v3.0.1/"
TIME_OF_DAY = "120000"   # timestamp used in filename: YYYYMMDDHHMMSS -> here HHMMSS = 120000
USER_AGENT = "download_ghrsst_py/1.1 (+https://your.domain/)"
CHUNK_SIZE = 1024 * 1024  # 1 MB
MAX_RETRIES = 5
BACKOFF_FACTOR = 1.0
REQUEST_TIMEOUT = (10, 60)  # connect timeout, read timeout (sec)

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("esacci_downloader")

# --- SESSION WITH RETRY ---
def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    retries = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=["GET", "HEAD"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

# --- BUILD URL AND FILENAME ---
def make_url_and_filename(date_obj):
    yyyy = date_obj.strftime("%Y")
    mm = date_obj.strftime("%m")
    dd = date_obj.strftime("%d")
    ymd = date_obj.strftime("%Y%m%d")
    if int(yyyy) > 2021:
        dataset = "ICDR3.0" # from 2022 the dataset is Interim-CDR
    else:
        dataset = "CDR3.0"
    filename = f"{ymd}{TIME_OF_DAY}-ESACCI-L4_GHRSST-SSTdepth-OSTIA-GLOB_{dataset}-v02.0-fv01.0.nc"
    url = urljoin(BASE_URL, f"{yyyy}/{mm}/{dd}/{filename}")
    return url, filename

# --- SINGLE DOWNLOAD (with resume) ---
def download_file(session, url, out_path, max_attempts=3):
    tmp_path = out_path + ".part"

    if os.path.exists(out_path):
        logger.info(f"Already exists: {out_path} -> skipping")
        return True

    resume_byte_pos = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
    headers = {}
    if resume_byte_pos:
        headers['Range'] = f"bytes={resume_byte_pos}-"

    attempts = 0
    while attempts < max_attempts:
        try:
            logger.info(f"Request: {url} (resume at {resume_byte_pos})")
            resp = session.get(url, stream=True, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 404:
                logger.warning(f"File not found (404): {url}")
                return False
            if resp.status_code not in (200, 206):
                logger.warning(f"Unexpected response {resp.status_code} for {url}")
                attempts += 1
                time.sleep(2 ** attempts)
                continue

            mode = "ab" if resume_byte_pos and resp.status_code == 206 else "wb"
            with open(tmp_path, mode) as fd:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        fd.write(chunk)
                fd.flush()

            os.replace(tmp_path, out_path)
            logger.info(f"Downloaded: {out_path}")
            return True

        except requests.RequestException as e:
            attempts += 1
            wait = BACKOFF_FACTOR * (2 ** (attempts - 1))
            logger.warning(f"Download error ({attempts}/{max_attempts}): {e}. Retrying in {wait}s")
            time.sleep(wait)
            resume_byte_pos = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
            headers['Range'] = f"bytes={resume_byte_pos}-"

    logger.error(f"Failed after {max_attempts} attempts: {url}")
    return False

# --- POSTPROCESSING ---
def postprocess(data_dir, start, end):
    logger.info("Starting post-processing with CDO...")

    years = sorted(set(range(start.year, end.year + 1)))
    for year in years:
        logger.info(f"Processing year {year}")
        
        # Find all files for this year
        files = sorted([f for f in os.listdir(data_dir) if f.startswith(str(year)) and f.endswith(".nc")])
        if not files:
            logger.warning(f"No files found for {year}, skipping")
            continue

        file_paths = [os.path.join(data_dir, f) for f in files]
        input_files = " ".join(file_paths)
        
        # Output file for yearly monthly averages
        temp_file = os.path.join(data_dir, f"temp_merged_{year}.nc")
        
        try:
            # Clean up any existing temporary file before starting
            if os.path.exists(temp_file):
                os.remove(temp_file)
                logger.info(f"Removed existing temporary file: {temp_file}")
            
            # Check if all target files already exist
            all_exist = True
            for variable in ["analysed_sst", "sea_ice_fraction"]:
                var_dir = os.path.join(data_dir, variable)
                var_output_file = os.path.join(var_dir, f"ESA-CCI-L4_v3.0.1_monthly_{year}_{variable}.nc")
                if not os.path.exists(var_output_file):
                    all_exist = False
                    break
            
            if all_exist:
                logger.info(f"All target files for {year} already exist, skipping processing")
                continue
            
            # Step 1: Merge all daily files for the year
            logger.info(f"Merging daily files for {year}...")
            merge_cmd = f"cdo mergetime {input_files} {temp_file}"
            result = subprocess.run(merge_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"CDO merge failed for {year}: {result.stderr}")
                continue
            
            # Step 2: Calculate monthly averages, select variable and fix timestamps
            for variable in ["analysed_sst", "sea_ice_fraction"]:
                # Create variable-specific folder
                var_dir = os.path.join(data_dir, variable)
                os.makedirs(var_dir, exist_ok=True)
                
                var_output_file = os.path.join(var_dir, f"ESA-CCI-L4_v3.0.1_monthly_{year}_{variable}.nc")
                
                # Check if this specific variable file already exists
                if os.path.exists(var_output_file):
                    logger.info(f"Target file already exists, skipping: {var_output_file}")
                    continue
                
                logger.info(f"Calculating monthly averages for {year}, variable: {variable}...")
                monthly_cmd = f"cdo -f nc4 -z zip settime,00:00:00 -setday,1 -monmean -selname,{variable} {temp_file} {var_output_file}"
                result = subprocess.run(monthly_cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"CDO monthly average failed for {year}, variable {variable}: {result.stderr}")
                    continue
                logger.info(f"Created monthly averages file: {var_output_file}")
                  
            # Clean up temporary file
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
        except Exception as e:
            logger.error(f"Error processing {year}: {e}")
            # Clean up temporary files in case of error
            if os.path.exists(temp_file):
                os.remove(temp_file)
            continue

    logger.info("Post-processing completed")

# --- MAIN ---
def main(args):
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    if end < start:
        raise SystemExit("End date must be >= start date")

    os.makedirs(args.out, exist_ok=True)
    session = make_session()

    cur = start
    successes, failures = 0, []
    while cur <= end:
        url, filename = make_url_and_filename(cur)
        out_path = os.path.join(args.out, filename)
        if args.dry_run:
            logger.info(f"[DRY RUN] URL: {url} -> {out_path}")
            successes += 1
        else:
            ok = download_file(session, url, out_path)
            if ok:
                successes += 1
            else:
                failures.append(cur)
        cur += timedelta(days=1)

    logger.info(f"Download completed: {successes} successes, {len(failures)} failed")
    if failures:
        logger.info("Failed dates:")
        for f in failures:
            logger.info(" - " + f.isoformat())

    if args.postproc and not args.dry_run:
        postprocess(args.out, start, end)


# --- REGRID FUNCTION ---
def regrid_var_output_files(data_dir, start, end):
    logger.info("Starting regridding with CDO remapcon to r360x180...")
    start_year = start.year
    end_year = end.year
    regridded_count = 0
    import re
    for variable in ["analysed_sst", "sea_ice_fraction"]:
        var_dir = os.path.join(data_dir, variable)
        if not os.path.isdir(var_dir):
            logger.warning(f"Directory not found: {var_dir}")
            continue
        for fname in os.listdir(var_dir):
            year = os.path.basename(fname).split("_")[3]
            if start_year <= int(year) <= end_year:
                in_file = os.path.join(var_dir, fname)
                out_file = in_file.replace(f"_{variable}.nc", f"_{variable}_r360x180.nc")
                if os.path.exists(out_file):
                    logger.info(f"Regridded file already exists, skipping: {out_file}")
                    continue
                cmd = f"cdo remapcon,r360x180 {in_file} {out_file}"
                logger.info(f"Regridding {in_file} -> {out_file}")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"CDO regrid failed for {in_file}: {result.stderr}")
                else:
                    logger.info(f"Created regridded file: {out_file}")
                    regridded_count += 1
    if regridded_count == 0:
        logger.warning("No files were regridded. Check year range and file availability.")
    else:
        logger.info(f"Regridding completed. {regridded_count} file(s) processed.")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="NetCDF CEDA GHRSST downloader with optional postprocessing")
    p.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p.add_argument("--out", required=True, help="Output folder")
    p.add_argument("--dry-run", action="store_true", help="Show URLs without downloading")
    p.add_argument("--postproc", action="store_true", help="Create yearly files of monthly averages using CDO (NC4 compressed, timestamps at midnight of first day of month)")
    p.add_argument("--regrid-only", action="store_true", help="Regrid var_output_file to r360x180 using CDO remapcon (no download/postproc)")
    args = p.parse_args()
    if args.regrid_only:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date()
        regrid_var_output_files(args.out, start, end)
    else:
        main(args)

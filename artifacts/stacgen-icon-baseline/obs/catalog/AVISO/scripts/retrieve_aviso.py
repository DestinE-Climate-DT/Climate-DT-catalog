#!/usr/bin/env python3
import os
import time
import cdsapi
import zipfile
import argparse

version = "vdt2024"
DIR = '/scratch/b/b382076/aviso'

# Argument parser: optional positional `year` to override the default range
parser = argparse.ArgumentParser(description="Retrieve AVISO data. Optionally override year to download a single year.")
parser.add_argument('year', nargs='?', type=int, help='Year to download (overrides default range)')
args = parser.parse_args()

if args.year:
    years = [args.year]
else:
    years = range(1993, 2025)

client = cdsapi.Client()
for year in years:
    for mon in range(1, 13):
        print(f"downloading aviso for year {year} month {mon}")
        dataset = "satellite-sea-level-global"
        request = {
        "variable": ["daily"],
        "year": [year],
        "month": [f"{mon:02d}"],
        "day": [
            "01", "02", "03",
            "04", "05", "06",
            "07", "08", "09",
            "10", "11", "12",
            "13", "14", "15",
            "16", "17", "18",
            "19", "20", "21",
            "22", "23", "24",
            "25", "26", "27",
            "28", "29", "30",
            "31"
        ],
        "version": version
        }
        output_file = f"{DIR}/aviso_ssh_L4_{year}{mon:02d}_{version}.zip"
        final = os.path.join(DIR, str(year), f"{mon:02d}")

        if not os.path.exists(output_file) and not os.path.exists(final):
            # Retry on UrlNoDataError from cdsapi (sometimes the server returns no data intermittently)
            max_retries = 5
            retry_delay = 5  # seconds, will multiply on each retry
            attempt = 0
            while True:
                try:
                    client.retrieve(dataset, request, output_file)
                    break
                except Exception as UrlNoDataError:
                    # Prefer the specific cdsapi error when available
                    if attempt <= max_retries:
                        attempt += 1
                        print(f"UrlNoDataError encountered, retry {attempt}/{max_retries} after {retry_delay}s")
                        time.sleep(retry_delay)
                        continue
                    # If not the specific error or exceeded retries, re-raise
                    raise

            os.makedirs(final, exist_ok=True)
            with zipfile.ZipFile(output_file, 'r') as zip_ref:
                zip_ref.extractall(final)
            os.remove(output_file)
        

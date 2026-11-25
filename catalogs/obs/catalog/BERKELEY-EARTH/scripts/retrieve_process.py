#!/usr/bin/env python3
"""
Script to download and process Berkeley Earth gridded temperature data
(mean, maximum and minimum temperature).
Adds the anomalies to the climatology, sets a monthly time axis
and fills the missing values with CDO.
"""

import sys
import os
import argparse
import urllib.request
import urllib.error
from pathlib import Path
import xarray as xr
import numpy as np
import pandas as pd
from cdo import Cdo
cdo = Cdo()


PRODUCTS = {
    'v1': {
        'url': 'https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Gridded',
        'filename': {'tavg': 'Land_and_Ocean_LatLong1.nc'}
        },
    'v2': {
        'url': 'https://storage.googleapis.com/berkeley-earth-temperature-hr/global/gridded',
        'filename': {
            'tavg': 'Global_TAVG_Gridded_1deg.nc',
            'tmax': 'Land_TMAX_Gridded_1deg.nc',
            'tmin': 'Land_TMIN_Gridded_1deg.nc'
            }
        },
    'v2-highres': {
        'url': 'https://storage.googleapis.com/berkeley-earth-temperature-hr/global/gridded',
        'filename': {
            'tavg': 'Global_TAVG_Gridded_0p25deg.nc',
            'tmax': 'Land_TMAX_Gridded_0p25deg.nc',
            'tmin': 'Land_TMIN_Gridded_0p25deg.nc'
            }
    }
}

# Output name and long name of each variable. Maximum and minimum temperature
# are land-only products: the ocean is kept missing when filling the gaps.
VARIABLES = {
    'tavg': {'name': '2t', 'long_name': 'Surface Temperature', 'land_only': False},
    'tmax': {'name': 'max_2t', 'long_name': 'Maximum Surface Temperature', 'land_only': True},
    'tmin': {'name': 'min_2t', 'long_name': 'Minimum Surface Temperature', 'land_only': True}
}

def download_berkeley_earth_file(output_dir, version='v2', variable='tavg'):
    """
    Download Berkeley Earth file from S3 repository
    
    Args:
        output_dir (str): Directory to save the file
        version (str): Version of the file to download
        variable (str): Variable to download (tavg, tmax or tmin)

    Returns:
        str: Path of downloaded file, None if error
    """

    filename = PRODUCTS[version]['filename'][variable]
    url = f"{PRODUCTS[version]['url']}/{filename}"
    output_path = Path(output_dir) / filename
    
    print(f"Downloading Berkeley Earth file from: {url}")
    print(f"Saving to: {output_path}")
    
    try:
        # Create directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Callback function to show progress
        def progress_hook(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100, (block_num * block_size * 100) // total_size)
                print(f"\rDownload progress: {percent}%", end='', flush=True)
        
        # Download the file
        urllib.request.urlretrieve(url, output_path, progress_hook)
        print(f"\nDownload completed: {output_path}")
        
        # Verify file was downloaded correctly
        if output_path.exists() and output_path.stat().st_size > 0:
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"File size: {file_size_mb:.2f} MB")
            return str(output_path)
        else:
            print("Error: Downloaded file is empty or doesn't exist")
            return None
            
    except urllib.error.URLError as e:
        print(f"Download error: {e}")
        return None
    except Exception as e:
        print(f"General download error: {e}")
        return None


def process_berkeley_earth_file(output_dir, year1=1979, year2=None, version='v2', variable='tavg'):
    """
    Process Berkeley Earth file applying all necessary transformations
    
    Args:
        output_dir (str): Directory to save the processed file
        year1 (int): selection starting year
        year2 (int): selection final year, None to keep all the available data
        version (str): Version of the file to process
        variable (str): Variable to process (tavg, tmax or tmin)
    """
    filename = PRODUCTS[version]['filename'][variable]
    input_file = Path(output_dir) / filename

    # load the data
    ds = xr.open_dataset(input_file)

    # create the full field
    years = np.floor(ds['time'].values).astype(int)
    frac = ds['time'].values - years
    months = (np.floor(frac * 12).astype(int) + 1)
    month_index = xr.DataArray(months - 1, dims=['time'], name='month_index')
    clim_for_time = ds['climatology'].isel(month_number=month_index)
    out = ds['temperature'] + clim_for_time

    # time axis adjustment
    start = pd.Timestamp(year=years[0], month=months[0], day=1)
    timeaxis = pd.date_range(start=start, periods=out.time.size, freq='MS')
    out = out.assign_coords(time=timeaxis)
    out.name = VARIABLES[variable]['name']
    out.attrs['long_name'] = VARIABLES[variable]['long_name']
    out.attrs['units'] = 'degC'

    #nan count per year and selection
    #nan_mask = out.isnull()
    #count = nan_mask.groupby('time.year').sum(dim=['time','latitude','longitude'])
    #count.year[count.where(count < 100).notnull()]

    #select from year1 to year2 (or to today)
    out = out.sel(time=slice(f'{year1}-01-01', f'{year2}-12-31' if year2 else None))
    year2 = out.time.dt.year.max().values

    # Salva temporaneamente e rimappa con extrapolation
    temp_file = Path(output_dir) / f'temp_in_{variable}.nc'
    if os.path.exists(temp_file):
        os.remove(temp_file)
    out.to_netcdf(temp_file)
    if 'highres' in version:
        resolution = '0.25'
    else:
        resolution = '1'
    # tavg keeps the original file name, other variables are tagged
    tag = '' if variable == 'tavg' else f'{variable}_'
    outfile = Path(output_dir) / Path(f'Berkeley-Earth_aqua-filled_{tag}{resolution}x{resolution}_{year1}-{year2}.nc')
    if os.path.exists(outfile):
        os.remove(outfile)
    if VARIABLES[variable]['land_only']:
        # fill the gaps, then keep only the cells which have data at least once (the land)
        cdo.ifthen(options='-f nc4 -z zip', input=f'-gtc,-1000 -timmax {temp_file} -fillmiss {temp_file}',
                   output=str(outfile))
    else:
        cdo.fillmiss(options='-f nc4 -z zip', input=str(temp_file), output=str(outfile))
    os.remove(temp_file)
    
def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Process Berkeley Earth files with CDO to set time axis and climatology"
    )
    parser.add_argument(
        "output_dir", 
        nargs='?',
        help="Path to output directory (optional if using --download)"
    )
    parser.add_argument(
        "-d", "--download",
        action="store_true",
        help="Download original file from Berkeley Earth before processing"
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download file only without processing"
    )
    parser.add_argument(
        "-v", "--version",
        choices=['v1', 'v2', 'v2-highres'],
        default='v2',
        help="Version of Berkeley Earth data to download (default: v2)"
    )
    parser.add_argument(
        "--variable",
        choices=list(VARIABLES),
        default='tavg',
        help="Variable to download: mean (tavg), maximum (tmax) or minimum (tmin) temperature (default: tavg)"
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=None,
        help="Last year to keep (default: all the available data)"
    )
    
    args = parser.parse_args()
    
    # If no input_file and no download requested, error
    if not args.output_dir and not args.download and not args.download_only:
        parser.error("You must specify an input file or use --download/--download-only")
    if args.variable not in PRODUCTS[args.version]['filename']:
        parser.error(f"Variable {args.variable} is not available for version {args.version}")
    
    if args.download or args.download_only:
        print("Download option enabled...")
        downloaded_file = download_berkeley_earth_file(
            args.output_dir, version=args.version, variable=args.variable)
        
        if not downloaded_file:
            print("Error downloading file")
            sys.exit(1)
        
        # If download-only, exit here
        if args.download_only:
            print(f"Download completed. File saved to: {downloaded_file}")
            sys.exit(0)
        
        # Otherwise use downloaded file as input
    
    # Process the file (no CDO verification needed)
    if not args.download_only:
        process_berkeley_earth_file(
            args.output_dir, year1=1979, year2=args.end_year, version=args.version, variable=args.variable)
        
    print("Success!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script to process Berkeley Earth Land_and_Ocean_LatLong1.nc data
Applies CDO to set monthly time axis from 1850 with hourly units
and adds temperature to climatology variable.
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


def download_berkeley_earth_file(output_dir, filename="Land_and_Ocean_LatLong1.nc"):
    """
    Download Berkeley Earth file from S3 repository
    
    Args:
        output_dir (str): Directory to save the file
        filename (str): Filename to save
    
    Returns:
        str: Path of downloaded file, None if error
    """
    url = f"https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Gridded/{filename}"
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


def process_berkeley_earth_file(input_file, year1=1979):
    """
    Process Berkeley Earth file applying all necessary transformations
    
    Args:
        input_file (str): Path to Land_and_Ocean_LatLong1.nc file
        year1 (str): selection starting year
    
    Returns:
        str: Path to processed file, None if error
    """
    input_path = Path(input_file)

    # load the data
    ds = xr.open_dataset(input_path)

    # create the full field
    years = np.floor(ds['time'].values).astype(int)
    frac = ds['time'].values - years
    months = (np.floor(frac * 12).astype(int) + 1)
    month_index = xr.DataArray(months - 1, dims=['time'], name='month_index')
    clim_for_time = ds['climatology'].isel(month_number=month_index)
    out = ds['temperature'] + clim_for_time

    # time axis adjustment
    timeaxis = pd.date_range(start=pd.Timestamp('1850-01-01T00:00:00'), periods=out.time.size, freq='MS')
    out = out.assign_coords(time=timeaxis)
    out.name = '2t'
    out.attrs['long_name'] = 'Surface Temperature'
    out.attrs['units'] = 'degC'

    #nan count per year and selection
    #nan_mask = out.isnull()
    #count = nan_mask.groupby('time.year').sum(dim=['time','latitude','longitude'])
    #count.year[count.where(count < 100).notnull()]

    #select from year1 to today
    year2=out.time.dt.year.max().values
    out = out.sel(time=slice(f'{year1}-01-01', None))

    # Salva temporaneamente e rimappa con extrapolation
    if os.path.exists('temp_in.nc'):
        os.remove('temp_in.nc')
    out.to_netcdf('temp_in.nc')
    outfile = f'Berkeley-Earth_aqua-filled_1x1_{year1}-{year2}.nc'
    if os.path.exists(outfile):
        os.remove(outfile)
    cdo.fillmiss(options='-f nc4 -z zip', input='temp_in.nc', output=outfile)
    os.remove('temp_in.nc')
    
def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Process Berkeley Earth files with CDO to set time axis and climatology"
    )
    parser.add_argument(
        "input_file", 
        nargs='?',
        help="Path to Land_and_Ocean_LatLong1.nc file to process (optional if using --download)"
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
    
    args = parser.parse_args()
    
    # If no input_file and no download requested, error
    if not args.input_file and not args.download and not args.download_only:
        parser.error("You must specify an input file or use --download/--download-only")
    # Determine output directory
    elif args.input_file:
        output_dir = Path(args.input_file).parent
    else:
        output_dir = Path.cwd()

    # Handle download if requested
    input_file_path = args.input_file
    
    if args.download or args.download_only:
        print("Download option enabled...")
        downloaded_file = download_berkeley_earth_file(output_dir)
        
        if not downloaded_file:
            print("Error downloading file")
            sys.exit(1)
        
        # If download-only, exit here
        if args.download_only:
            print(f"Download completed. File saved to: {downloaded_file}")
            sys.exit(0)
        
        # Otherwise use downloaded file as input
        input_file_path = downloaded_file
        print(f"Will use downloaded file: {input_file_path}")
    
    # Process the file (no CDO verification needed)
    if not args.download_only:
        process_berkeley_earth_file(
            input_file_path, year1=1979)
        
    print("Success!")


if __name__ == "__main__":
    main()

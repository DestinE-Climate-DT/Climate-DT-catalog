#!/usr/bin/env python3
"""
Script to process Berkeley Earth Land_and_Ocean_LatLong1.nc data
Applies CDO to set monthly time axis from 1850 with hourly units
and adds temperature to climatology variable.
"""

import sys
import subprocess
import argparse
import urllib.request
import urllib.error
from pathlib import Path


def run_cdo_command(command, input_file, output_file):
    """
    Execute a CDO command
    
    Args:
        command (str): CDO command to execute
        input_file (str): Input file
        output_file (str): Output file
    
    Returns:
        bool: True if command executed successfully
    """
    cmd = f"cdo {command} {input_file} {output_file}"
    print(f"Executing: {cmd}")
    subprocess.run(cmd, shell=True, check=True, 
                              capture_output=True, text=True)


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


def process_berkeley_earth_file(input_file, output_dir=None, start_year=1850):
    """
    Process Berkeley Earth file applying all necessary transformations
    
    Args:
        input_file (str): Path to Land_and_Ocean_LatLong1.nc file
        output_dir (str): Output directory (optional)
        start_year (int): Start year for time axis
    
    Returns:
        str: Path to processed file, None if error
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"Error: File {input_file} does not exist")
        return None
    
    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Intermediate files
    temp1 = output_dir / "temp1_time_axis.nc"
    final_output = output_dir / f"processed_{input_path.name}"
    
    print(f"Processing file: {input_file}")
    print(f"Final output: {final_output}")
    
    try:
        # Step 1: Set monthly time axis from 1850 and hourly units
        print("\nStep 1: Setting monthly time axis and hourly units...")
        command = f"settunits,hours -settaxis,{start_year}-01-01,00:00:00,1mon"
        run_cdo_command(command, input_file, temp1)
        
        # Step 2: Sum temperature and climatology variables
        print("\nStep 2: Summing temperature and climatology variables...")
        command = "expr,2m_temperature=temperature+climatology"
        run_cdo_command(command, temp1, final_output)
        
        # Clean up temporary files
        if temp1.exists():
            temp1.unlink()
        
        print(f"\nProcessing completed successfully!")
        print(f"Processed file saved to: {final_output}")
        
        return str(final_output)
        
    except Exception as e:
        print(f"Error during processing: {e}")
        # Clean up temporary files in case of error
        if temp1.exists():
            temp1.unlink()
        return None


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
        "--out", 
        help="Output directory (default: current directory)"
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
    if args.out:
        output_dir = Path(args.out)
    elif args.input_file:
        output_dir = Path(args.input_file).parent
    else:
        output_dir = Path.cwd()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
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
        result = process_berkeley_earth_file(
            input_file_path, 
            output_dir
        )
        
        if result:
            print(f"\nSuccess! Processed file: {result}")
            sys.exit(0)
        else:
            print("\nError processing file")
            sys.exit(1)


if __name__ == "__main__":
    main()

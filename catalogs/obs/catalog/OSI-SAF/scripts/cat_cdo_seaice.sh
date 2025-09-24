#!/bin/bash

HEM=${1:-"nh"}

in_dir="./data"
out_dir="."

#in_dir="./osi-430a-${HEM}"
#out_dir="."

# Loop over the years
for year in $(seq 1979 2020); do
#for year in $(seq 2021 2025); do

    echo "Processing year $year for hemisphere ${HEM}..."
    
    # Define output file name
    outfile="${out_dir}/ice_conc_${HEM}_ease2-250_cdr-v3p1_${year}.nc"
    #outfile="${out_dir}/ice_conc_${HEM}_ease2-250_cdr-v3p0_${year}.nc"
    
    # Apply cdo cat to all matching files
    cdo cat ${in_dir}/ice_conc_${HEM}_ease2-250_cdr-v3p1_${year}*.nc $outfile
    #cdo cat ${in_dir}/ice_conc_${HEM}_ease2-250_icdr*-v3p0_${year}*.nc $outfile
    
    echo " -> Created $outfile"
done

echo "All years processed."

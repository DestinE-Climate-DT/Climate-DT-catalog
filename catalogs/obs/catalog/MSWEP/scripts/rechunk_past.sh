#!/bin/bash
#SBATCH --job-name=3hra
#SBATCH --mail-type=ALL
#SBATCH --time=770:00:00
#SBATCH --output=/data/datasets/obs/MSWEP_V280/log/3hra_%j.log
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1 
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1

cd /data/datasets/obs/MSWEP_V280/Past

INDIR=3hourly
OUTDIR=3hourly_byyear_rechunked

mkdir -p $OUTDIR

export CDO_NC_CHUNKSIZE=lat=1800,lon=3600,time=1

y1=1979
y2=1990

for ((y=y1; y<=y2; y++)); do

 echo $y
 cdo -z zip_1 -k grid -f nc4 -cat [ $INDIR/${y}???.??.nc ] $OUTDIR/MSWEP_v280_3hourly_$y.nc

done




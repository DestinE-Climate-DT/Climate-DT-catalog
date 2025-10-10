#!/bin/bash

cd Past 

cd Monthly
ln -s ../../NRT/Monthly/202012.nc
cd ..

INDIR=Monthly
OUTDIR=Monthly_byyear_rechunked

mkdir -p $OUTDIR

export CDO_NC_CHUNKSIZE=lat=1800,lon=3600,time=1

y1=1979
y2=2020

for ((y=y1; y<=y2; y++)); do

 echo $y
 cdo -z zip_1 -k grid -f nc4 cat [ $INDIR/${y}??.nc ] $OUTDIR/MSWEP_v280_monthly_$y.nc

done




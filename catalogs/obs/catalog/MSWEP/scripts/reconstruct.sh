#!/bin/bash

cd Past

cd Daily
mkdir -p reconstructed
cdo settime,0 -setattribute,precipitation@units="mm d-1"  -mulc,8 -timmean -cat [ ../3hourly/1979001.* ]  reconstructed/1979001.nc
ncks -C -O -x -v time_bnds reconstructed/1979001.nc reconstructed/1979001_notimebnds.nc
ncatted -O -a bounds,time,d,, reconstructed/1979001_notimebnds.nc
mv reconstructed/1979001_notimebnds.nc reconstructed/1979001.nc
ln -s reconstructed/1979001.nc .

cd ../Monthly
mkdir -p reconstructed
cdo setattribute,precipitation@units="mm month-1"  -timsum -cat [ ../Daily/197900?.nc ../Daily/197901?.nc ../Daily/197902?.nc ../Daily/1979030.nc ../Daily/1979031.nc ]  reconstructed/197901.nc
ncks -C -O -x -v time_bnds reconstructed/197901.nc reconstructed/197901_notimebnds.nc
ncatted -O -a bounds,time,d,, reconstructed/197901_notimebnds.nc
mv reconstructed/197901_notimebnds.nc reconstructed/197901.nc
ln -s reconstructed/197901.nc .

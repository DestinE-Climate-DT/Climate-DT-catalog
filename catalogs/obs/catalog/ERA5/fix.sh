#!/bin/bash
# this script fixes the time axis of ERA5 monthly files.
# cumulated fluxes has 06:00:00 as time stamp, but should have 00:00:00
# currently the CDS-retriever does not fix this, so this script has to be added

#DIR=/work/bb1153/b382076/ERA5/mon
DIR=/pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/ERA5/mon/new

varlist="evaporation surface_net_solar_radiation_clear_sky surface_net_solar_radiation surface_net_thermal_radiation_clear_sky surface_net_thermal_radiation surface_sensible_heat_flux surface_solar_radiation_downwards surface_thermal_radiation_downwards top_net_solar_radiation_clear_sky top_net_solar_radiation top_net_thermal_radiation_clear_sky top_net_thermal_radiation total_precipitation"
for var in $varlist ; do
	file=$DIR/ERA5_${var}_mon_full_sfc_1940-2024.nc
	echo $file
	cdo -f nc4 -z zip settunits,hours -settaxis,1940-01-01,00:00:00,1mon $file $DIR/test.nc
	mv $DIR/test.nc $file
done

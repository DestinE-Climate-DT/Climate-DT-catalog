#!/bin/bash

DIR=/work/bb1153/b382076/ERA5/mon

varlist="evaporation surface_net_solar_radiation_clear_sky surface_net_solar_radiation surface_net_thermal_radiation_clear_sky surface_net_thermal_radiation surface_sensible_heat_flux surface_solar_radiation_downwards surface_thermal_radiation_downwards top_net_solar_radiation_clear_sky top_net_solar_radiation top_net_thermal_radiation_clear_sky top_net_thermal_radiation total_precipitation"
for var in $varlist ; do
	file=$DIR/ERA5_${var}_mon_full_sfc_1940-2024.nc
	echo $file
	cdo -f nc4 -z zip settaxis,1940-01-01,00:00:00,1mon $file $DIR/test.nc
	mv $DIR/test.nc $file
done

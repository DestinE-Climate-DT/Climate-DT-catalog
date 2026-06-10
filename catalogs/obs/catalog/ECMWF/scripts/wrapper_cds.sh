#!/bin/bash
# This script works only for monthly files, it is run on Levante, and 
# looks for availalbe data and then extend it using CDS features
# it will not remove older files
# it might be more convienent to not run the update flag, and manually cat the files

STOREDIR='/work/bb1153/b382076/ERA5'
TMPDIR='/work/bb1153/b382076/ERA5'
CDSPATH=/home/b/b382076/CDS-retriever
CDSconfig=/home/b/b382076/CDS-retriever/config.yaml

year1=1940
year2=2024

varlist=($(for f in $STOREDIR/mon/ERA5_*.nc; do
    basename "$f" | sed -E 's/^ERA5_([^_]+(_[^_]+)*)_mon_.*$/\1/'
done))

# define which vars are 3D
threeD_vars=("temperature" "u_component_of_wind" "v_component_of_wind" "specific_humidity")

for variable in "${varlist[@]}" ; do
	if [[ " ${threeD_vars[*]} " == *" $variable "* ]]; then
        	levelout=plev8
        else
        	levelout=sfc
        fi
	echo $variable
	CDSDIR=$STOREDIR/${variable}/mon
	mkdir -p $CDSDIR
	cp $STOREDIR/mon/*${variable}*nc $CDSDIR
	python3 $CDSPATH/ERA5_retrieve_postproc.py -c "$CDSconfig" -v "$variable" --outputdir $STOREDIR --tmpdir $TMPDIR --levelout $levelout -u
	cp $CDSDIR/*${variable}*nc $STOREDIR/mon
	rm -rf $CDSDIR
done

# this path has to be adjusted
DIR=$STOREDIR/mon

# fix to enforce time axis for fluxes variables
varlist="evaporation surface_net_solar_radiation_clear_sky surface_net_solar_radiation surface_net_thermal_radiation_clear_sky surface_net_thermal_radiation surface_sensible_heat_flux surface_solar_radiation_downwards surface_thermal_radiation_downwards top_net_solar_radiation_clear_sky top_net_solar_radiation top_net_thermal_radiation_clear_sky top_net_thermal_radiation total_precipitation surface_latent_heat_flux "
for var in $varlist ; do
	file=$DIR/ERA5_${var}_mon_full_sfc_${year1}-${year2}.nc
	echo $file
	cdo -f nc4 -z zip settunits,hours -settaxis,${year1}-01-01,00:00:00,1mon $file $DIR/test.nc
	mv $DIR/test.nc $file
done




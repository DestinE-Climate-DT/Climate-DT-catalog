#!/bin/bash
#This script works only for monthly files

STOREDIR='/work/bb1153/b382076/ERA5'
TMPDIR='/work/bb1153/b382076/ERA5'
varlist='2m_temperature evaporation'
CDSPATH=/home/b/b382076/CDS-retriever
CDSconfig=/home/b/b382076/CDS-retriever/config.yaml


varlist=($(for f in $STOREDIR/mon/ERA5_*.nc; do
    basename "$f" | sed -E 's/^ERA5_([^_]+(_[^_]+)*)_mon_.*$/\1/'
done))

# define which vars are 3D
threeD_vars=("temperature" "u_component_of_wind" "v_component_of_wind" "specific_humidity")

for variable in "${varlist[@]}" ; do
	if [[ " ${threeD_vars[*]} " == *" $variable "* ]]; then
        	levelout=plev19
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



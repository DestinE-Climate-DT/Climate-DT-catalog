DIR=/work/bb1153/b382076/ERA5/mon
DIRNEW=/work/bb1153/b382076/ERA5/mon_rename
year1=1940
year2=2025

mkdir -p $DIRNEW
for file in $DIR/ERA5_*_mon_full_sfc_${year1}-${year2}.nc ; do
    filename=$(basename $file)
    echo $filename

    rm -f $DIRNEW/test.grb
    cdo -f grb copy $DIR/$filename $DIRNEW/test.grb
    cdo -f nc4 -z zip --eccodes copy $DIRNEW/test.grb $DIRNEW/$filename
    rm $DIRNEW/test.grb

    varold=$(cdo -s showname $DIR/$filename)
    varnew=$(cdo -s showname $DIRNEW/$filename)
    echo "Name changed from $varold to $varnew"
done

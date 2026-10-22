#!/bin/bash
#SBATCH --job-name=3hre
#SBATCH --mail-type=ALL
#SBATCH --time=770:00:00
#SBATCH --output=/data/datasets/obs/MSWEP_V280/log/3hre_%j.log
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1 
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1

cd /aqua/work/users/aqua-dvc/datasets/MSWEP/v2.8/netcdf

# >>> mamba initialize >>>
# !! Contents within this block are managed by 'mamba shell init' !!
export MAMBA_EXE='/aqua/work/users/mnurisso/miniforge3/bin/mamba';
export MAMBA_ROOT_PREFIX='/aqua/work/users/mnurisso/miniforge3';
__mamba_setup="$("$MAMBA_EXE" shell hook --shell bash --root-prefix "$MAMBA_ROOT_PREFIX" 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__mamba_setup"
else
    alias mamba="$MAMBA_EXE"  # Fallback on help from mamba activate
fi
mamba activate aqua-dev

INDIR=NRT
OUTDIR=NRT_rechunked

ulimit -n 4096

mkdir -p $OUTDIR

export CDO_NC_CHUNKSIZE=lat=1800,lon=3600,time=1

y1=2021
y2=2025

for ((y=y1; y<=y2; y++)); do

 echo $y
 cdo -z zip_1 -k grid -f nc4 -cat -apply,-selname,precipitation [ $INDIR/${y}??.nc ] $OUTDIR/MSWEP_v280_monthly_$y.nc

 cdo settime,0 $OUTDIR/MSWEP_v280_monthly_$y.nc $OUTDIR/MSWEP_v280_monthly_${y}_fixed.nc
 mv $OUTDIR/MSWEP_v280_monthly_${y}_fixed.nc $OUTDIR/MSWEP_v280_monthly_$y.nc

done    




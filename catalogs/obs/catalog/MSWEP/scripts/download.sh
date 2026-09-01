#!/bin/bash
#
# Download MSWEP v3 data from the GoogleDrive shared by the GloH2O maintainers.
#
# Access to the GoogleDrive folder must be requested beforehand by following the
# "Apply" link on https://www.gloh2o.org/mswep/. Once access is granted, the
# GoogleDrive remote must be configured for rclone (see
# https://rclone.org/drive/), and the mamba/conda environment "rclone" must
# provide the `rclone` executable.
#
# Usage:
#   ./download.sh -r <resolution> -a <archive> -o <outdir> [-v <version>]
#
#   -r  resolution: one of "3hourly", "daily", "monthly" (default: 3hourly)
#   -a  archive: one of "Past", "NRT" (default: Past)
#   -o  output directory where data will be synced (required)
#   -v  MSWEP GoogleDrive version folder name (default: MSWEP_V3)
#
# Example:
#   ./download.sh -r 3hourly -a NRT -o /aqua/work/users/MSWEP/MSWEP_V3/3hourly/NRT

set -e

RESOLUTION="3hourly"
ARCHIVE="Past"
VERSION="MSWEP_V3"
OUTDIR=""

usage() {
    echo "Usage: $0 -o <outdir> [-r 3hourly|daily|monthly] [-a Past|NRT] [-v <gdrive-version-folder>]"
    exit 1
}

while getopts "r:a:o:v:h" opt; do
    case "$opt" in
        r) RESOLUTION="$OPTARG" ;;
        a) ARCHIVE="$OPTARG" ;;
        o) OUTDIR="$OPTARG" ;;
        v) VERSION="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

if [ -z "$OUTDIR" ]; then
    echo "Error: output directory (-o) is required"
    usage
fi

case "$RESOLUTION" in
    3hourly) REMOTE_DIR="3hourly" ;;
    daily) REMOTE_DIR="Daily" ;;
    monthly) REMOTE_DIR="Monthly" ;;
    *) echo "Error: invalid resolution '$RESOLUTION'"; usage ;;
esac

case "$ARCHIVE" in
    Past|NRT) ;;
    *) echo "Error: invalid archive '$ARCHIVE'"; usage ;;
esac

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
mamba activate rclone
# <<< mamba initialize <<<

mkdir -p "$OUTDIR"

echo "Downloading MSWEP ${VERSION} ${ARCHIVE}/${REMOTE_DIR} into ${OUTDIR}"

rclone sync -v --progress \
    --transfers 4 --checkers 8 \
    --drive-shared-with-me \
    GoogleDrive:/${VERSION}/${ARCHIVE}/${REMOTE_DIR} \
    "$OUTDIR"

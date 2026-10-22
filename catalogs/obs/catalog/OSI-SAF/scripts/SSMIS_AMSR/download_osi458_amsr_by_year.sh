#!/usr/bin/env bash
#
# Robust year-by-year downloader for OSI SAF OSI-458 AMSR CDR
# from Copernicus Marine.
#
# Pinned provenance:
#   version: 202603
#   part:    originalGrid
#
# The master manifests are created once, then split by year.
# Each yearly request uses Copernicus Marine's internal parallel downloader.
#
# Run from:
#   /pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/OSI-SAF/OSI-AQUA
#
# Usage:
#   MAX_CONCURRENT=8 bash download_osi458_amsr_by_year.sh
#
# Optional:
#   START_YEAR=2015 MAX_CONCURRENT=8 bash download_osi458_amsr_by_year.sh
#   HEMISPHERE=nh bash download_osi458_amsr_by_year.sh
#   HEMISPHERE=sh bash download_osi458_amsr_by_year.sh
#
# HEMISPHERE defaults to "both".
#

set -euo pipefail

ROOT="${1:-./AMSR}"
ROOT="$(mkdir -p "$ROOT" && cd "$ROOT" && pwd)"

MAX_CONCURRENT="${MAX_CONCURRENT:-8}"
START_YEAR="${START_YEAR:-2002}"
END_YEAR="${END_YEAR:-2020}"
HEMISPHERE="${HEMISPHERE:-both}"

DATASET_VERSION="202603"
DATASET_PART="originalGrid"

NH_ID="osisaf_obs-si_glo_phy_sic-north_my_amsr_cdr_P1D-m"
SH_ID="osisaf_obs-si_glo_phy_sic-south_my_amsr_cdr_P1D-m"

NH_DIR="$ROOT/daily/osi-458-v3p0-nh"
SH_DIR="$ROOT/daily/osi-458-v3p0-sh"

MANIFEST_DIR="$ROOT/daily/manifests"
YEAR_DIR="$MANIFEST_DIR/by-year"

NH_MASTER="$MANIFEST_DIR/osi458_nh_files.txt"
SH_MASTER="$MANIFEST_DIR/osi458_sh_files.txt"

mkdir -p "$NH_DIR" "$SH_DIR" "$MANIFEST_DIR" "$YEAR_DIR" "$ROOT/monthly"

if ! command -v copernicusmarine >/dev/null 2>&1; then
    echo "ERROR: copernicusmarine CLI not found." >&2
    exit 1
fi

if ! [[ "$MAX_CONCURRENT" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: MAX_CONCURRENT must be a positive integer." >&2
    exit 1
fi

if ! [[ "$START_YEAR" =~ ^[0-9]{4}$ && "$END_YEAR" =~ ^[0-9]{4}$ ]]; then
    echo "ERROR: START_YEAR and END_YEAR must be four-digit years." >&2
    exit 1
fi

case "$HEMISPHERE" in
    nh|sh|both) ;;
    *)
        echo "ERROR: HEMISPHERE must be nh, sh, or both." >&2
        exit 1
        ;;
esac

echo "OSI SAF OSI-458 year-by-year downloader"
echo "ROOT                : $ROOT"
echo "Dataset version     : $DATASET_VERSION"
echo "Dataset part        : $DATASET_PART"
echo "Years               : $START_YEAR-$END_YEAR"
echo "Hemisphere          : $HEMISPHERE"
echo "Concurrent requests : $MAX_CONCURRENT"
echo

make_master_manifest () {
    local dataset_id="$1"
    local outfile="$2"
    local label="$3"

    if [[ -s "$outfile" ]]; then
        echo "[$label] Using existing master manifest:"
        echo "       $outfile"
    else
        echo "[$label] Creating master manifest ..."
        copernicusmarine get \
            --dataset-id "$dataset_id" \
            --dataset-version "$DATASET_VERSION" \
            --dataset-part "$DATASET_PART" \
            --create-file-list "$outfile" \
            --log-level WARN
    fi

    local n
    n=$(grep -c -v '^[[:space:]]*$' "$outfile" || true)
    echo "[$label] Master manifest contains $n files."
    echo
}

download_years () {
    local hemi="$1"
    local dataset_id="$2"
    local master="$3"
    local outdir="$4"

    local year year_manifest expected local_count

    echo "============================================================"
    echo "Starting hemisphere: ${hemi^^}"
    echo "============================================================"
    echo

    for year in $(seq "$START_YEAR" "$END_YEAR"); do
        year_manifest="$YEAR_DIR/osi458_${hemi}_${year}.txt"

        # Paths in the Copernicus manifest contain /YYYY/MM/.
        grep "/${year}/" "$master" > "$year_manifest" || true

        expected=$(grep -c -v '^[[:space:]]*$' "$year_manifest" || true)

        if [[ "$expected" -eq 0 ]]; then
            echo "[${hemi^^} $year] No upstream files; skipping."
            continue
        fi

        local_count=$(
            find "$outdir" -maxdepth 1 -type f \
                -name "ice_conc_${hemi}_ease2-250_cdr-v3p0-amsr_${year}*.nc" \
                | wc -l | tr -d '[:space:]'
        )

        echo "[${hemi^^} $year] upstream=$expected  local=$local_count"

        if [[ "$local_count" -eq "$expected" ]]; then
            echo "[${hemi^^} $year] already complete; skipping."
            echo
            continue
        fi

        echo "[${hemi^^} $year] downloading ..."

        copernicusmarine get \
            --dataset-id "$dataset_id" \
            --dataset-version "$DATASET_VERSION" \
            --dataset-part "$DATASET_PART" \
            --file-list "$year_manifest" \
            --output-directory "$outdir" \
            --no-directories \
            --max-concurrent-requests "$MAX_CONCURRENT" \
            --log-level INFO

        local_count=$(
            find "$outdir" -maxdepth 1 -type f \
                -name "ice_conc_${hemi}_ease2-250_cdr-v3p0-amsr_${year}*.nc" \
                | wc -l | tr -d '[:space:]'
        )

        if [[ "$local_count" -ne "$expected" ]]; then
            echo "ERROR: ${hemi^^} $year incomplete after download:" >&2
            echo "       local=$local_count expected=$expected" >&2
            exit 1
        fi

        echo "[${hemi^^} $year] complete: $local_count/$expected files."
        echo
    done

    echo "${hemi^^} requested years complete."
    echo
}

if [[ "$HEMISPHERE" == "nh" || "$HEMISPHERE" == "both" ]]; then
    make_master_manifest "$NH_ID" "$NH_MASTER" "NH"
fi

if [[ "$HEMISPHERE" == "sh" || "$HEMISPHERE" == "both" ]]; then
    make_master_manifest "$SH_ID" "$SH_MASTER" "SH"
fi

if [[ "$HEMISPHERE" == "nh" || "$HEMISPHERE" == "both" ]]; then
    download_years "nh" "$NH_ID" "$NH_MASTER" "$NH_DIR"
fi

if [[ "$HEMISPHERE" == "sh" || "$HEMISPHERE" == "both" ]]; then
    download_years "sh" "$SH_ID" "$SH_MASTER" "$SH_DIR"
fi

echo "============================================================"
echo "OSI-458 download finished."
echo "============================================================"

if [[ "$HEMISPHERE" == "nh" || "$HEMISPHERE" == "both" ]]; then
    echo "NH total local files:"
    find "$NH_DIR" -maxdepth 1 -type f -name '*.nc' | wc -l
    du -sh "$NH_DIR" 2>/dev/null || true
fi

if [[ "$HEMISPHERE" == "sh" || "$HEMISPHERE" == "both" ]]; then
    echo "SH total local files:"
    find "$SH_DIR" -maxdepth 1 -type f -name '*.nc' | wc -l
    du -sh "$SH_DIR" 2>/dev/null || true
fi


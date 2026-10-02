#!/usr/bin/env bash
#
# Final OSI-430-a v3.0 update: Jan-Sep 2025
# Robust THREDDS downloader using curl (no HTTP Range/resume requests).
#
# Usage:
#   bash update_osi430a_ssmis_2025_v2.sh
# or
#   bash update_osi430a_ssmis_2025_v2.sh /path/to/OSI-AQUA
# Note: the script was run at: /pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/OSI-SAF/OSI-AQUA

set -euo pipefail
shopt -s nullglob

ROOT="${1:-./SSMIS}"
ROOT="$(cd "$ROOT" && pwd)"

BASE_CAT="https://thredds.met.no/thredds/catalog/osisaf/met.no/reprocessed/ice/conc_cra_files"
BASE_FS="https://thredds.met.no/thredds/fileServer"

YEAR=2025
FIRST_MONTH=01
LAST_MONTH=09

for cmd in curl cdo grep sed sort; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: required command '$cmd' not found." >&2
        exit 1
    }
done

echo "ROOT: $ROOT"
echo "Downloading final OSI-430-a period: ${YEAR}-${FIRST_MONTH} through ${YEAR}-${LAST_MONTH}"
echo

mkdir -p "$ROOT/daily_cat" "$ROOT/monthly"

validate_netcdf () {
    local file="$1"
    [[ -s "$file" ]] && cdo -s sinfo "$file" >/dev/null 2>&1
}

download_one () {
    local url="$1"
    local outdir="$2"
    local name outfile tmp

    name="$(basename "$url")"
    outfile="${outdir}/${name}"
    tmp="${outfile}.part"

    # Keep already valid files, including any successfully downloaded
    # before a previous interrupted run.
    if [[ -f "$outfile" ]]; then
        if validate_netcdf "$outfile"; then
            echo "  [OK]   $name"
            return 0
        else
            echo "  [BAD]  $name -- removing incomplete/corrupt file"
            rm -f "$outfile"
        fi
    fi

    rm -f "$tmp"

    echo "  [GET]  $name"
    curl \
        --fail \
        --location \
        --retry 5 \
        --retry-delay 2 \
        --connect-timeout 30 \
        --output "$tmp" \
        "$url"

    if ! validate_netcdf "$tmp"; then
        echo "ERROR: downloaded file is not a valid readable NetCDF: $name" >&2
        rm -f "$tmp"
        return 1
    fi

    mv "$tmp" "$outfile"
}

for HEMI in nh sh; do
    echo "============================================================"
    echo "Hemisphere: $HEMI"
    echo "============================================================"

    DAILY_DIR="$ROOT/daily/osi-430a-v3p0-${HEMI}/daily"
    LIST_DIR="$ROOT/daily/osi-430a-v3p0-${HEMI}/url_lists_2025"

    mkdir -p "$DAILY_DIR" "$LIST_DIR"

    # ------------------------------------------------------------
    # Download Jan-Sep only. OSI-430-a terminates 2025-09-30.
    # ------------------------------------------------------------
    for M in $(seq -w "$FIRST_MONTH" "$LAST_MONTH"); do
        LIST_FILE="$LIST_DIR/${HEMI}_${YEAR}${M}.txt"
        CAT_URL="$BASE_CAT/$YEAR/$M/catalog.xml"

        echo "[INDEX] $HEMI ${YEAR}-${M}"

        XML="$(curl --fail --silent --show-error --location "$CAT_URL")"

        printf '%s\n' "$XML" \
            | grep 'urlPath="' \
            | grep "ice_conc_${HEMI}_ease2-250_icdr-v3p0_${YEAR}${M}" \
            | sed -E "s@.*urlPath=\"([^\"]+)\".*@${BASE_FS}/\1@" \
            | sort -u \
            > "$LIST_FILE"

        NURL=$(wc -l < "$LIST_FILE" | tr -d '[:space:]')
        if [[ "$NURL" -eq 0 ]]; then
            echo "ERROR: no $HEMI OSI-430-a URLs found for ${YEAR}-${M}" >&2
            exit 1
        fi

        echo "        $NURL URL(s)"

        while IFS= read -r url; do
            [[ -n "$url" ]] || continue
            download_one "$url" "$DAILY_DIR"
        done < "$LIST_FILE"
    done

    # ------------------------------------------------------------
    # Validate local coverage month-by-month.
    # ------------------------------------------------------------
    echo
    echo "Valid local files by month:"
    TOTAL=0

    for M in $(seq -w "$FIRST_MONTH" "$LAST_MONTH"); do
        FILES=(
            "$DAILY_DIR"/ice_conc_"${HEMI}"_ease2-250_icdr-v3p0_"${YEAR}${M}"*.nc
        )

        VALID=0
        for f in "${FILES[@]}"; do
            if validate_netcdf "$f"; then
                VALID=$((VALID + 1))
            fi
        done

        if [[ "$VALID" -eq 0 ]]; then
            echo "ERROR: no valid files for $HEMI ${YEAR}-${M}" >&2
            exit 1
        fi

        printf "  %s-%s : %3d\n" "$YEAR" "$M" "$VALID"
        TOTAL=$((TOTAL + VALID))
    done

    echo "  total   : $TOTAL"

    # ------------------------------------------------------------
    # Concatenate Jan-Sep daily records.
    # Bash glob sorts filenames chronologically because YYYYMMDD
    # is embedded in the name.
    # ------------------------------------------------------------
    DAILY_2025=(
        "$DAILY_DIR"/ice_conc_"${HEMI}"_ease2-250_icdr-v3p0_"${YEAR}"*.nc
    )

    ANNUAL="$ROOT/daily_cat/ice_conc_${HEMI}_ease2-250_cdr-v3p0_${YEAR}.nc"

    echo
    echo "[CDO CAT] ${#DAILY_2025[@]} files -> $ANNUAL"
    rm -f "$ANNUAL"
    cdo -O cat "${DAILY_2025[@]}" "$ANNUAL"

    # ------------------------------------------------------------
    # Monthly Jan-Sep means.
    # ------------------------------------------------------------
    PARTIAL_MONTHLY="$ROOT/monthly/ice_conc_${HEMI}_ease2-250_cdr-v3p0_monthly_202501-202509.nc"

    echo "[MONMEAN] -> $PARTIAL_MONTHLY"
    rm -f "$PARTIAL_MONTHLY"
    cdo -O monmean "$ANNUAL" "$PARTIAL_MONTHLY"

    NMONTHS=$(cdo -s ntime "$PARTIAL_MONTHLY" | tr -d '[:space:]')
    if [[ "$NMONTHS" -ne 9 ]]; then
        echo "ERROR: expected 9 monthly timesteps, got $NMONTHS" >&2
        exit 1
    fi

    # ------------------------------------------------------------
    # Append to existing 1979-2024 monthly file.
    # Keep old product untouched.
    # ------------------------------------------------------------
    OLD_MONTHLY="$ROOT/monthly/ice_conc_${HEMI}_ease2-250_cdr_v3_monthly_1979-2024.nc"
    FINAL_MONTHLY="$ROOT/monthly/ice_conc_${HEMI}_ease2-250_ssmis_cdr_v3_monthly_197901-202509.nc"
    TMP_FINAL="${FINAL_MONTHLY}.tmp.nc"

    [[ -f "$OLD_MONTHLY" ]] || {
        echo "ERROR: missing existing monthly file: $OLD_MONTHLY" >&2
        exit 1
    }

    OLD_NTIME=$(cdo -s ntime "$OLD_MONTHLY" | tr -d '[:space:]')
    EXPECTED=$((OLD_NTIME + 9))

    echo "[MERGETIME]"
    rm -f "$TMP_FINAL" "$FINAL_MONTHLY"
    cdo -O mergetime "$OLD_MONTHLY" "$PARTIAL_MONTHLY" "$TMP_FINAL"

    FINAL_NTIME=$(cdo -s ntime "$TMP_FINAL" | tr -d '[:space:]')

    if [[ "$FINAL_NTIME" -ne "$EXPECTED" ]]; then
        echo "ERROR: final file has $FINAL_NTIME timesteps; expected $EXPECTED" >&2
        rm -f "$TMP_FINAL"
        exit 1
    fi

    mv "$TMP_FINAL" "$FINAL_MONTHLY"

    echo
    echo "[DONE] $HEMI"
    echo "  Daily Jan-Sep 2025 : $TOTAL"
    echo "  Monthly 2025       : $NMONTHS"
    echo "  Final monthly ntime: $FINAL_NTIME"
    echo "  Output:"
    echo "    $FINAL_MONTHLY"
    echo
done

echo "All done."


#!/usr/bin/env bash
#
# =============================================================================
# Build OSI SAF AMSR yearly daily_cat and final monthly products
# =============================================================================
#
# PURPOSE
# -------
# Process the locally downloaded EUMETSAT OSI SAF AMSR sea-ice concentration
# products into the structure required by the Climate-DT/AQUA catalogue.
#
# The AMSR record combines:
#
#   OSI-458 : CDR,  AMSR-E + AMSR2, 2002-2020
#             daily files: cdr-v3p0-amsr
#
#   OSI-438 : ICDR, AMSR2,          2021-present
#             daily files: icdr-v3p0-amsr
#
# OSI-438 is the operational continuation of OSI-458.
#
#
# PROCESSING WORKFLOW
# -------------------
# For each hemisphere:
#
#   daily OSI-458 / OSI-438 files
#              |
#              | cdo cat (one year at a time)
#              v
#   daily_cat/YYYY
#              |
#              | cdo mergetime (temporary merged daily file)
#              | cdo monmean
#              v
#   one final multi-year monthly AMSR product
#
# One cached monthly file is retained per year. These are processing
# intermediates only (not separate catalogue products) and make future updates
# much faster by avoiding repeated monmean over the full daily archive.
#
#
# EXPECTED INPUT
# --------------
#   AMSR/
#   - daily/
#     - osi-458-v3p0-nh/
#     - osi-458-v3p0-sh/
#     - osi-438-v3p0-nh/
#     - osi-438-v3p0-sh/
#   - daily_cat/
#   - monthly/
#
#
# OUTPUT
# ------
#   AMSR/
#   - daily_cat/
#     - ice_conc_nh_ease2-250_cdr-v3p0-amsr_2002.nc
#     - ...
#     - ice_conc_nh_ease2-250_icdr-v3p0-amsr_2021.nc
#     - ...
#     - corresponding SH files
# 
#   - monthly/
#     - ice_conc_nh_ease2-250_amsr_v3_monthly_YYYYMM-YYYYMM.nc
#     - ice_conc_sh_ease2-250_amsr_v3_monthly_YYYYMM-YYYYMM.nc
#     - mask_nh.nc
#     - mask_sh.nc
#
#
# MISSING DATA
# ------------
# No missing days or months are synthesized or interpolated.
#
# A month with no daily observations is absent from the monthly time axis.
# A partially sampled month is averaged from the observations actually
# available. This reproduces the processing philosophy used for the SSMIS
# branch and preserves the real AMSR-E -> AMSR2 observing gap.
#
#
# INCREMENTAL UPDATES
# -------------------
# Existing yearly daily_cat files are skipped if:
#   - their number of timesteps equals the number of current daily source files;
#   - no source daily file is newer than the daily_cat output.
#
# Thus, after downloading new OSI-438 files (e.g. 2026), rerunning this script
# rebuilds only the affected yearly daily_cat file(s), then regenerates the
# final monthly record from all yearly daily_cat files.
#
#
# OSI-458 / OSI-438 COMPATIBILITY
# --------------------------------
# Representative OSI-458 and OSI-438 files are compared using:
#
#   cdo griddes
#   cdo showname
#
# Processing stops if their grids or variable lists differ.
#
#
# MASK GENERATION
# ---------------
# The SSMIS masks were generated from a monthly sea-ice concentration field,
# not from a generic external land/sea mask. This script reproduces that logic
# for AMSR:
#
#   select MASK_YEAR (default 2020)
#   select first monthly timestep
#   select ice_conc
#   rename ice_conc -> mask
#   apply gtc,-1
#
# Therefore mask_nh.nc and mask_sh.nc carry AMSR-specific provenance.
#
#
# GRID FILES
# ----------
# grid_osi-saf-aqua_nh.nc and grid_osi-saf-aqua_sh.nc are not generated here.
# They may be reused from the SSMIS branch only after exact grid compatibility
# has been verified.
#
#
# USAGE
# -----
# From inside AMSR/:
#
#   bash process_osi_saf_amsr_v2.sh
#
# From OSI-AQUA/:
#
#   bash process_osi_saf_amsr_v2.sh AMSR
#
# One hemisphere only:
#
#   HEMISPHERE=nh bash process_osi_saf_amsr_v2.sh
#   HEMISPHERE=sh bash process_osi_saf_amsr_v2.sh
#
# Force complete rebuild:
#
#   FORCE=1 bash process_osi_saf_amsr_v2.sh
#
# Do not generate/update masks:
#
#   GENERATE_MASK=0 bash process_osi_saf_amsr_v2.sh
#
# Use a different reference year for masks:
#
#   MASK_YEAR=2020 bash process_osi_saf_amsr_v2.sh
#
#
# OPTIONAL ENVIRONMENT VARIABLES
# ------------------------------
#   HEMISPHERE    nh, sh, or both      default: both
#   FORCE         0 or 1               default: 0
#   CHECK_COMPAT  0 or 1               default: 1
#   GENERATE_MASK 0 or 1               default: 1
#   MASK_YEAR     reference mask year  default: 2020
#
# =============================================================================

set -euo pipefail

HEMISPHERE="${HEMISPHERE:-both}"
FORCE="${FORCE:-0}"
CHECK_COMPAT="${CHECK_COMPAT:-1}"
GENERATE_MASK="${GENERATE_MASK:-1}"
MASK_YEAR="${MASK_YEAR:-2020}"

if [[ $# -ge 1 ]]; then
    ROOT="$1"
elif [[ -d "./daily/osi-458-v3p0-nh" || -d "./daily/osi-438-v3p0-nh" ]]; then
    ROOT="."
elif [[ -d "./AMSR/daily" ]]; then
    ROOT="./AMSR"
else
    echo "ERROR: cannot locate AMSR directory." >&2
    exit 1
fi

ROOT="$(cd "$ROOT" && pwd)"
DAILY="$ROOT/daily"
DAILY_CAT="$ROOT/daily_cat"
MONTHLY="$ROOT/monthly"
MONTHLY_YEARLY="$MONTHLY/yearly"

mkdir -p "$DAILY_CAT" "$MONTHLY" "$MONTHLY_YEARLY"

for cmd in cdo find sort sed grep diff mktemp awk tr cut; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: required command '$cmd' not found." >&2
        exit 1
    }
done

case "$HEMISPHERE" in
    nh|sh|both) ;;
    *) echo "ERROR: HEMISPHERE must be nh, sh, or both." >&2; exit 1 ;;
esac

echo "OSI SAF AMSR post-processing"
echo "ROOT          : $ROOT"
echo "Hemisphere    : $HEMISPHERE"
echo "Force rebuild : $FORCE"
echo "Generate mask : $GENERATE_MASK"
echo "Mask year     : $MASK_YEAR"
echo

product_for_year () {
    local year="$1"
    if (( year <= 2020 )); then
        printf '%s\n' "458 cdr-v3p0-amsr"
    else
        printf '%s\n' "438 icdr-v3p0-amsr"
    fi
}

available_years () {
    local hemi="$1"
    {
        find "$DAILY/osi-458-v3p0-${hemi}" -maxdepth 1 -type f \
            -name "ice_conc_${hemi}_ease2-250_cdr-v3p0-amsr_????????1200.nc" \
            -printf '%f\n' 2>/dev/null || true
        find "$DAILY/osi-438-v3p0-${hemi}" -maxdepth 1 -type f \
            -name "ice_conc_${hemi}_ease2-250_icdr-v3p0-amsr_????????1200.nc" \
            -printf '%f\n' 2>/dev/null || true
    } \
    | sed -E 's/.*_([0-9]{4})[0-9]{4}1200\.nc/\1/' \
    | grep -E '^[0-9]{4}$' \
    | sort -u
}

check_compatibility () {
    local hemi="$1"
    [[ "$CHECK_COMPAT" == "1" ]] || return 0

    local f458 f438
    f458="$(find "$DAILY/osi-458-v3p0-${hemi}" -maxdepth 1 -type f -name '*.nc' 2>/dev/null | sort | head -n 1 || true)"
    f438="$(find "$DAILY/osi-438-v3p0-${hemi}" -maxdepth 1 -type f -name '*.nc' 2>/dev/null | sort | head -n 1 || true)"

    if [[ -z "$f458" || -z "$f438" ]]; then
        echo "[${hemi^^}] WARNING: cannot compare OSI-458/438; representative file missing."
        return 0
    fi

    local g458 g438 v458 v438
    g458="$(mktemp)"
    g438="$(mktemp)"
    v458="$(mktemp)"
    v438="$(mktemp)"

    cdo -s griddes "$f458" > "$g458"
    cdo -s griddes "$f438" > "$g438"
    cdo -s showname "$f458" | tr -s ' ' | sed 's/^ //;s/ $//' > "$v458"
    cdo -s showname "$f438" | tr -s ' ' | sed 's/^ //;s/ $//' > "$v438"

    if ! diff -q "$g458" "$g438" >/dev/null; then
        echo "ERROR: ${hemi^^} OSI-458 and OSI-438 grids differ." >&2
        diff -u "$g458" "$g438" || true
        rm -f "$g458" "$g438" "$v458" "$v438"
        exit 1
    fi

    if ! diff -q "$v458" "$v438" >/dev/null; then
        echo "ERROR: ${hemi^^} OSI-458 and OSI-438 variable lists differ." >&2
        diff -u "$v458" "$v438" || true
        rm -f "$g458" "$g438" "$v458" "$v438"
        exit 1
    fi

    rm -f "$g458" "$g438" "$v458" "$v438"
    echo "[${hemi^^}] OSI-458/438 grid and variable compatibility: OK"
}

daily_cat_up_to_date () {
    local outfile="$1"
    local source_dir="$2"
    local pattern="$3"
    local expected="$4"

    [[ "$FORCE" != "1" ]] || return 1
    [[ -s "$outfile" ]] || return 1

    local ntime
    ntime="$(cdo -s ntime "$outfile" 2>/dev/null || echo 0)"
    [[ "$ntime" -eq "$expected" ]] || return 1

    if find "$source_dir" -maxdepth 1 -type f -name "$pattern" -newer "$outfile" \
        -print -quit | grep -q .; then
        return 1
    fi

    return 0
}

count_unique_months () {
    local -a cats=("$@")
    local f
    for f in "${cats[@]}"; do
        cdo -s showdate "$f" \
        | tr ' ' '\n' \
        | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' \
        | cut -c1-7
    done | sort -u | wc -l | tr -d '[:space:]'
}

process_hemisphere () {
    local hemi="$1"

    echo
    echo "============================================================"
    echo "Processing ${hemi^^}"
    echo "============================================================"

    check_compatibility "$hemi"

    local years
    years="$(available_years "$hemi")"
    [[ -n "$years" ]] || {
        echo "ERROR: no ${hemi^^} AMSR daily files found." >&2
        exit 1
    }

    echo "[${hemi^^}] years: $(echo "$years" | tr '\n' ' ')"

    local year product tag source_dir pattern daily_out tmp
    local count ntime
    local -a files
    local -a cats=()

    for year in $years; do
        read -r product tag <<< "$(product_for_year "$year")"
        source_dir="$DAILY/osi-${product}-v3p0-${hemi}"
        pattern="ice_conc_${hemi}_ease2-250_${tag}_${year}????1200.nc"

        mapfile -t files < <(
            find "$source_dir" -maxdepth 1 -type f -name "$pattern" | sort
        )

        count="${#files[@]}"
        (( count > 0 )) || continue

        daily_out="$DAILY_CAT/ice_conc_${hemi}_ease2-250_${tag}_${year}.nc"

        echo
        echo "[${hemi^^} $year] source daily files: $count"

        if daily_cat_up_to_date "$daily_out" "$source_dir" "$pattern" "$count"; then
            echo "[${hemi^^} $year] daily_cat already up-to-date."
        else
            echo "[${hemi^^} $year] building daily_cat ..."
            tmp="${daily_out}.tmp"
            rm -f "$tmp"

            cdo -O cat "${files[@]}" "$tmp"

            ntime="$(cdo -s ntime "$tmp")"
            if [[ "$ntime" -ne "$count" ]]; then
                echo "ERROR: ${hemi^^} $year daily_cat has $ntime timesteps; expected $count." >&2
                rm -f "$tmp"
                exit 1
            fi

            mv "$tmp" "$daily_out"
            echo "[${hemi^^} $year] daily_cat complete: $ntime timesteps."
        fi

        cats+=("$daily_out")
    done

    (( ${#cats[@]} > 0 )) || {
        echo "ERROR: no ${hemi^^} yearly daily_cat files available." >&2
        exit 1
    }

    # -------------------------------------------------------------------------
    # Build/update one cached monthly file per year.
    # These files are operational intermediates: they avoid re-reading the full
    # daily archive every time the combined monthly product is regenerated.
    # -------------------------------------------------------------------------
    local -a monthly_years=()
    local cat monthly_year year_label monthly_n expected_year_months

    for cat in "${cats[@]}"; do
        year_label="$(basename "$cat" | sed -E 's/.*_([0-9]{4})\.nc$/\1/')"

        if (( year_label <= 2020 )); then
            monthly_year="$MONTHLY_YEARLY/ice_conc_${hemi}_ease2-250_cdr-v3p0-amsr_monthly_${year_label}.nc"
        else
            monthly_year="$MONTHLY_YEARLY/ice_conc_${hemi}_ease2-250_icdr-v3p0-amsr_monthly_${year_label}.nc"
        fi

        expected_year_months="$(
            cdo -s showdate "$cat" \
            | tr ' ' '\n' \
            | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' \
            | cut -c1-7 \
            | sort -u \
            | wc -l \
            | tr -d '[:space:]'
        )"

        local rebuild_monthly_year=0

        if [[ "$FORCE" == "1" || ! -s "$monthly_year" || "$cat" -nt "$monthly_year" ]]; then
            rebuild_monthly_year=1
        else
            monthly_n="$(cdo -s ntime "$monthly_year" 2>/dev/null || echo 0)"
            [[ "$monthly_n" -eq "$expected_year_months" ]] || rebuild_monthly_year=1
        fi

        if [[ "$rebuild_monthly_year" -eq 1 ]]; then
            echo "[${hemi^^} $year_label] building cached monthly means ..."
            tmp="${monthly_year}.tmp.nc"
            rm -f "$tmp"

            cdo -O monmean "$cat" "$tmp"

            monthly_n="$(cdo -s ntime "$tmp")"
            if [[ "$monthly_n" -ne "$expected_year_months" ]]; then
                echo "ERROR: ${hemi^^} $year_label monthly cache has $monthly_n timesteps; expected $expected_year_months." >&2
                rm -f "$tmp"
                exit 1
            fi

            mv "$tmp" "$monthly_year"
        else
            echo "[${hemi^^} $year_label] cached monthly file already up-to-date."
        fi

        monthly_years+=("$monthly_year")
    done

    # -------------------------------------------------------------------------
    # Merge the cached yearly monthly files into the final multi-year product.
    # -------------------------------------------------------------------------
    local last_index=$(( ${#monthly_years[@]} - 1 ))
    local first_date last_date first_ym last_ym

    first_date="$(
        cdo -s showdate "${monthly_years[0]}" \
        | tr ' ' '\n' \
        | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' \
        | head -n 1
    )"

    last_date="$(
        cdo -s showdate "${monthly_years[$last_index]}" \
        | tr ' ' '\n' \
        | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' \
        | tail -n 1
    )"

    first_ym="${first_date:0:7}"; first_ym="${first_ym//-/}"
    last_ym="${last_date:0:7}";   last_ym="${last_ym//-/}"

    local final="$MONTHLY/ice_conc_${hemi}_ease2-250_amsr_v3_monthly_${first_ym}-${last_ym}.nc"

    local expected_months=0 f
    for f in "${monthly_years[@]}"; do
        monthly_n="$(cdo -s ntime "$f")"
        expected_months=$((expected_months + monthly_n))
    done

    local rebuild_final=0
    if [[ "$FORCE" == "1" || ! -s "$final" ]]; then
        rebuild_final=1
    else
        local final_n
        final_n="$(cdo -s ntime "$final" 2>/dev/null || echo 0)"

        if [[ "$final_n" -ne "$expected_months" ]]; then
            rebuild_final=1
        else
            for f in "${monthly_years[@]}"; do
                if [[ "$f" -nt "$final" ]]; then
                    rebuild_final=1
                    break
                fi
            done
        fi
    fi

    if [[ "$rebuild_final" -eq 1 ]]; then
        echo
        echo "[${hemi^^}] merging cached yearly monthly files ..."
        echo "[${hemi^^}] expected monthly steps : $expected_months"

        tmp="${final}.tmp.nc"
        rm -f "$tmp"

        cdo -O mergetime "${monthly_years[@]}" "$tmp"

        local final_n
        final_n="$(cdo -s ntime "$tmp")"

        if [[ "$final_n" -ne "$expected_months" ]]; then
            echo "ERROR: ${hemi^^} final monthly product has $final_n timesteps; expected $expected_months." >&2
            rm -f "$tmp"
            exit 1
        fi

        mv "$tmp" "$final"

        echo "[${hemi^^}] monthly product complete:"
        echo "    $final"
        echo "[${hemi^^}] timesteps: $final_n"
    else
        echo
        echo "[${hemi^^}] monthly product already up-to-date:"
        echo "    $final"
    fi

    echo "[${hemi^^}] first monthly timestamp:"
    cdo -s showtimestamp "$final" | tr ' ' '\n' | grep -v '^$' | head -n 1

    echo "[${hemi^^}] last monthly timestamp:"
    cdo -s showtimestamp "$final" | tr ' ' '\n' | grep -v '^$' | tail -n 1

    if [[ "$GENERATE_MASK" == "1" ]]; then
        local mask="$MONTHLY/mask_${hemi}.nc"

        if ! cdo -s showyear "$final" | tr ' ' '\n' | grep -qx "$MASK_YEAR"; then
            echo "ERROR: MASK_YEAR=$MASK_YEAR is not present in $final." >&2
            exit 1
        fi

        echo "[${hemi^^}] generating AMSR mask from first monthly timestep of $MASK_YEAR ..."

        #tmp="${mask}.tmp"
	tmp="${mask%.nc}.tmp.nc"
        rm -f "$tmp"

        cdo -O gtc,-1 \
            -chname,ice_conc,mask \
            -selname,ice_conc \
            -seltimestep,1 \
            -selyear,"$MASK_YEAR" \
            "$final" "$tmp"

        mv "$tmp" "$mask"

        echo "[${hemi^^}] mask written:"
        echo "    $mask"
    fi
}

if [[ "$HEMISPHERE" == "nh" || "$HEMISPHERE" == "both" ]]; then
    process_hemisphere "nh"
fi

if [[ "$HEMISPHERE" == "sh" || "$HEMISPHERE" == "both" ]]; then
    process_hemisphere "sh"
fi

echo
echo "============================================================"
echo "AMSR post-processing complete."
echo "============================================================"


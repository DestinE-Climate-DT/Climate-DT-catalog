#!/usr/bin/env bash
#!/usr/bin/env bash
#
# =============================================================================
# OSI SAF OSI-438 v3 AMSR2 ICDR incremental downloader
# =============================================================================
#
# DESCRIPTION
# -----------
# Download the EUMETSAT OSI SAF Global Sea Ice Concentration Interim Climate
# Data Record (ICDR) OSI-438, release 3, for both the Northern and Southern
# Hemispheres from the Copernicus Marine Data Store.
#
# OSI-438 is the AMSR2-based continuation of the OSI-458 Climate Data Record:
#
#     OSI-458 : AMSR-E / AMSR2 CDR, 2002-2020
#     OSI-438 : AMSR2 ICDR,        2021-present
#
# This script is intended to maintain the OSI-438 component of the
# Climate-DT/AQUA observational sea-ice dataset. It is incremental by design:
# rerunning it refreshes the current upstream inventory and downloads only
# files that are not already available locally.
#
#
# DATA SOURCE
# -----------
# Copernicus Marine product:
#
#     SEAICE_GLO_SEAICE_L4_REP_OBSERVATIONS_011_009
#
# Copernicus Marine dataset IDs:
#
#   Northern Hemisphere:
#     osisaf_obs-si_glo_phy_sic-north_my_amsr_icdr_P1D-m
#
#   Southern Hemisphere:
#     osisaf_obs-si_glo_phy_sic-south_my_amsr_icdr_P1D-m
#
# The "originalGrid" dataset part is used in order to retrieve the native
# OSI SAF EASE2 25-km grid rather than a harmonised/regridded representation.
#
# Original producer files are retrieved with:
#
#     copernicusmarine get
#
# rather than "copernicusmarine subset".
#
#
# EXPECTED FILE TYPE
# ------------------
# Only final OSI-438 ICDR v3 AMSR files are retained:
#
#   ice_conc_nh_ease2-250_icdr-v3p0-amsr_YYYYMMDD1200.nc
#   ice_conc_sh_ease2-250_icdr-v3p0-amsr_YYYYMMDD1200.nc
#
# Fast-track/intermediate products such as "icdrft" are deliberately excluded.
#
#
# DEFAULT TIME RANGE
# ------------------
# The default acquisition period is:
#
#     2021-01-01 through 2025-12-31
#
# This can be extended without modifying the script, e.g.:
#
#     END_DATE=2026-12-31 bash download_osi438_amsr_incremental.sh
#
# or, to retrieve all currently available upstream data:
#
#     END_DATE=latest bash download_osi438_amsr_incremental.sh
#
# No interpolation or artificial files are generated for dates that are
# genuinely absent from the upstream OSI SAF archive.
#
#
# INCREMENTAL UPDATE LOGIC
# ------------------------
# On every run the script:
#
#   1. Queries Copernicus Marine and creates a fresh authoritative upstream
#      file inventory.
#
#   2. Selects only final OSI-438 v3 AMSR files.
#
#   3. Restricts the upstream inventory to START_DATE..END_DATE.
#
#   4. Splits the requested inventory by year to avoid submitting very large
#      file lists to a single Copernicus Marine "get" request.
#
#   5. Compares every expected upstream filename against the corresponding
#      local directory.
#
#   6. Treats an existing non-empty local file as already downloaded.
#
#   7. Creates a "missing" manifest containing only files that still need
#      to be retrieved.
#
#   8. Downloads only those missing files, using Copernicus Marine's internal
#      parallel downloader.
#
#   9. Verifies that all requested upstream files are present locally after
#      the download.
#
# Therefore the script can safely be rerun. For example, after downloading
# 2021-2025, a future run extending END_DATE into 2026 will skip the complete
# 2021-2025 archive and retrieve only files that are newly available/missing.
#
#
# LOCAL DIRECTORY STRUCTURE
# -------------------------
# The script assumes it is run from the OSI-AQUA directory and creates/uses:
#
#   AMSR/
#   - daily/
#     - osi-458-v3p0-nh/          # existing OSI-458 CDR, untouched
#     - osi-458-v3p0-sh/          # existing OSI-458 CDR, untouched
#     - osi-438-v3p0-nh/          # OSI-438 NH daily files
#     - osi-438-v3p0-sh/          # OSI-438 SH daily files
#     - manifests/
#       - osi-438-v3p0/
#       - upstream/          # full current upstream inventory
#       - requested-range/   # inventory for requested dates
#       - by-year/           # yearly manifests
#       - missing/           # files missing locally
#   - monthly/                      # reserved for later monthly processing
#
#
# COPERNICUS MARINE DATASET VERSION
# ---------------------------------
# By default DATASET_VERSION is left unset. The Copernicus Marine Toolbox
# therefore uses the latest currently available catalogue version.
#
# This is intentional for OSI-438 because it is an operationally extended ICDR.
#
# For a reproducible historical acquisition, a catalogue version can instead
# be explicitly pinned, for example:
#
#     DATASET_VERSION=202603 \
#     END_DATE=2025-12-31 \
#     bash download_osi438_amsr_incremental.sh
#
#
# REQUIREMENTS
# ------------
#   - copernicusmarine command-line client
#   - valid Copernicus Marine credentials
#   - standard Unix utilities: grep, sed, sort, find, wc
#
# The user should authenticate before running the script:
#
#     copernicusmarine login
#
# Optional NetCDF validation requires:
#
#     cdo
#
#
# USAGE
# -----
# Standard acquisition of OSI-438 for 2021-2025:
#
#     MAX_CONCURRENT=8 bash download_osi438_amsr_incremental.sh
#
# Inspect upstream/local status without downloading:
#
#     DISCOVER_ONLY=1 bash download_osi438_amsr_incremental.sh
#
# Update through the end of 2026:
#
#     END_DATE=2026-12-31 \
#     MAX_CONCURRENT=8 \
#     bash download_osi438_amsr_incremental.sh
#
# Update through the latest data currently available upstream:
#
#     END_DATE=latest \
#     MAX_CONCURRENT=8 \
#     bash download_osi438_amsr_incremental.sh
#
# Northern Hemisphere only:
#
#     HEMISPHERE=nh bash download_osi438_amsr_incremental.sh
#
# Southern Hemisphere only:
#
#     HEMISPHERE=sh bash download_osi438_amsr_incremental.sh
#
# Validate newly downloaded NetCDF files with CDO:
#
#     VERIFY_NETCDF=1 \
#     MAX_CONCURRENT=8 \
#     bash download_osi438_amsr_incremental.sh
#
#
# OPTIONAL ENVIRONMENT VARIABLES
# ------------------------------
#   START_DATE       First requested date in YYYY-MM-DD format.
#                    Default: 2021-01-01
#
#   END_DATE         Last requested date in YYYY-MM-DD format, or "latest".
#                    Default: 2025-12-31
#
#   HEMISPHERE       nh, sh, or both.
#                    Default: both
#
#   MAX_CONCURRENT   Maximum number of concurrent Copernicus Marine download
#                    requests.
#                    Default: 8
#
#   DISCOVER_ONLY    If set to 1, refresh inventories and report missing files
#                    without downloading anything.
#                    Default: 0
#
#   DATASET_VERSION  Optional Copernicus Marine catalogue-version label.
#                    Default: unset -> latest available version
#
#   DATASET_PART     Copernicus Marine dataset part.
#                    Default: originalGrid
#
#   VERIFY_NETCDF    If set to 1, validate newly downloaded files using
#                    "cdo -s sinfo".
#                    Default: 0
#
#
# NOTES
# -----
# - Existing non-empty files are never intentionally downloaded again.
#
# - Upstream missing dates remain missing. The script does not interpolate,
#   synthesize or otherwise fill gaps in the daily OSI-438 record.
#
# - Monthly means are NOT generated by this script. Daily OSI-438 acquisition
#   and monthly processing are intentionally kept as separate workflow steps.
#
# - OSI-458 and OSI-438 remain in separate local directories so that the
#   original CDR/ICDR provenance is preserved before construction of the
#   combined AMSR monthly Climate-DT/AQUA product.
#
# =============================================================================

set -euo pipefail

ROOT="${1:-./AMSR}"
ROOT="$(mkdir -p "$ROOT" && cd "$ROOT" && pwd)"

START_DATE="${START_DATE:-2021-01-01}"
END_DATE="${END_DATE:-2025-12-31}"
MAX_CONCURRENT="${MAX_CONCURRENT:-8}"
DISCOVER_ONLY="${DISCOVER_ONLY:-0}"
HEMISPHERE="${HEMISPHERE:-both}"
VERIFY_NETCDF="${VERIFY_NETCDF:-0}"
DATASET_VERSION="${DATASET_VERSION:-}"
DATASET_PART="${DATASET_PART:-originalGrid}"

NH_ID="osisaf_obs-si_glo_phy_sic-north_my_amsr_icdr_P1D-m"
SH_ID="osisaf_obs-si_glo_phy_sic-south_my_amsr_icdr_P1D-m"

NH_DIR="$ROOT/daily/osi-438-v3p0-nh"
SH_DIR="$ROOT/daily/osi-438-v3p0-sh"

MANIFEST_DIR="$ROOT/daily/manifests/osi-438-v3p0"
UPSTREAM_DIR="$MANIFEST_DIR/upstream"
RANGE_DIR="$MANIFEST_DIR/requested-range"
YEAR_DIR="$MANIFEST_DIR/by-year"
MISSING_DIR="$MANIFEST_DIR/missing"

mkdir -p "$NH_DIR" "$SH_DIR" "$UPSTREAM_DIR" "$RANGE_DIR" "$YEAR_DIR" "$MISSING_DIR" "$ROOT/monthly"

for cmd in copernicusmarine grep sed sort find wc; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: required command '$cmd' was not found." >&2
        exit 1
    }
done

[[ "$MAX_CONCURRENT" =~ ^[1-9][0-9]*$ ]] || {
    echo "ERROR: MAX_CONCURRENT must be a positive integer." >&2
    exit 1
}

case "$HEMISPHERE" in
    nh|sh|both) ;;
    *) echo "ERROR: HEMISPHERE must be nh, sh, or both." >&2; exit 1 ;;
esac

[[ "$START_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || {
    echo "ERROR: START_DATE must be YYYY-MM-DD." >&2
    exit 1
}

if [[ "$END_DATE" != "latest" ]] && ! [[ "$END_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "ERROR: END_DATE must be YYYY-MM-DD or 'latest'." >&2
    exit 1
fi

START_COMPACT="${START_DATE//-/}"
if [[ "$END_DATE" == "latest" ]]; then
    END_COMPACT=""
else
    END_COMPACT="${END_DATE//-/}"
fi

if [[ -n "$END_COMPACT" && "$END_COMPACT" < "$START_COMPACT" ]]; then
    echo "ERROR: END_DATE precedes START_DATE." >&2
    exit 1
fi

VERSION_ARGS=()
if [[ -n "$DATASET_VERSION" ]]; then
    VERSION_ARGS=(--dataset-version "$DATASET_VERSION")
fi

echo "OSI SAF OSI-438 v3 incremental downloader"
echo "ROOT                : $ROOT"
echo "Requested range     : $START_DATE -> $END_DATE"
echo "Dataset part        : $DATASET_PART"
if [[ -n "$DATASET_VERSION" ]]; then
    echo "Dataset version     : $DATASET_VERSION (pinned)"
else
    echo "Dataset version     : latest available"
fi
echo "Hemisphere          : $HEMISPHERE"
echo "Concurrent requests : $MAX_CONCURRENT"
echo

refresh_manifest () {
    local hemi="$1"
    local dataset_id="$2"
    local outfile="$3"
    # Copernicus Marine requires --create-file-list output names to end
    # explicitly in .txt or .csv. Keep the unfiltered upstream inventory
    # in a valid .txt temporary file, then filter it locally.
    local stem="${outfile%.txt}"
    local raw="${stem}_all.txt"
    local tmp="${stem}_filtered.tmp"

    rm -f "$raw" "$tmp"

    echo "[${hemi^^}] Refreshing upstream manifest ..."

    copernicusmarine get \
        --dataset-id "$dataset_id" \
        "${VERSION_ARGS[@]}" \
        --dataset-part "$DATASET_PART" \
        --create-file-list "$raw" \
        --log-level INFO

    grep -E "/ice_conc_${hemi}_ease2-250_icdr-v3p0-amsr_[0-9]{12}\.nc$" \
        "$raw" | sort -u > "$tmp" || true

    rm -f "$raw"

    [[ -s "$tmp" ]] || {
        echo "ERROR: no final OSI-438 ${hemi^^} files found upstream." >&2
        exit 1
    }

    mv "$tmp" "$outfile"
    echo "[${hemi^^}] Upstream files: $(wc -l < "$outfile")"
}

filter_requested_range () {
    local hemi="$1"
    local upstream="$2"
    local outfile="$3"

    : > "$outfile"

    while IFS= read -r url; do
        [[ -n "$url" ]] || continue
        local name="${url##*/}"

        if [[ "$name" =~ _([0-9]{8})[0-9]{4}\.nc$ ]]; then
            local ymd="${BASH_REMATCH[1]}"
            [[ "$ymd" < "$START_COMPACT" ]] && continue
            [[ -n "$END_COMPACT" && "$ymd" > "$END_COMPACT" ]] && continue
            printf '%s\n' "$url" >> "$outfile"
        fi
    done < "$upstream"

    [[ -s "$outfile" ]] || {
        echo "ERROR: no ${hemi^^} files fall inside requested range." >&2
        exit 1
    }

    echo "[${hemi^^}] Files in requested range: $(wc -l < "$outfile")"
}

build_missing_manifest () {
    local upstream_year="$1"
    local outdir="$2"
    local missing="$3"

    : > "$missing"

    while IFS= read -r url; do
        [[ -n "$url" ]] || continue
        local name="${url##*/}"
        [[ -s "$outdir/$name" ]] || printf '%s\n' "$url" >> "$missing"
    done < "$upstream_year"
}

verify_manifest_locally () {
    local manifest="$1"
    local outdir="$2"
    local bad=0
    local url name

    while IFS= read -r url; do
        [[ -n "$url" ]] || continue
        name="${url##*/}"
        if [[ ! -s "$outdir/$name" ]]; then
            echo "MISSING: $outdir/$name" >&2
            bad=$((bad + 1))
        fi
    done < "$manifest"

    [[ "$bad" -eq 0 ]]
}

verify_new_netcdf () {
    local manifest="$1"
    local outdir="$2"

    [[ "$VERIFY_NETCDF" == "1" ]] || return 0

    command -v cdo >/dev/null 2>&1 || {
        echo "ERROR: VERIFY_NETCDF=1 but cdo is unavailable." >&2
        return 1
    }

    local url name
    while IFS= read -r url; do
        [[ -n "$url" ]] || continue
        name="${url##*/}"
        cdo -s sinfo "$outdir/$name" >/dev/null 2>&1 || {
            echo "ERROR: invalid NetCDF: $outdir/$name" >&2
            return 1
        }
    done < "$manifest"
}

process_hemisphere () {
    local hemi="$1"
    local dataset_id="$2"
    local outdir="$3"

    local upstream="$UPSTREAM_DIR/osi438_${hemi}_upstream.txt"
    local requested="$RANGE_DIR/osi438_${hemi}_${START_COMPACT}-${END_COMPACT:-latest}.txt"

    refresh_manifest "$hemi" "$dataset_id" "$upstream"
    filter_requested_range "$hemi" "$upstream" "$requested"

    local years
    years="$(sed -E 's/.*_([0-9]{4})[0-9]{8}\.nc$/\1/' "$requested" | sort -u)"

    echo
    echo "============================================================"
    echo "Processing ${hemi^^}"
    echo "============================================================"

    local year year_manifest missing_manifest expected missing present

    for year in $years; do
        year_manifest="$YEAR_DIR/osi438_${hemi}_${year}.txt"
        missing_manifest="$MISSING_DIR/osi438_${hemi}_${year}_missing.txt"

        grep -E "_${year}[0-9]{8}\.nc$" "$requested" > "$year_manifest" || true
        expected=$(wc -l < "$year_manifest" | tr -d '[:space:]')
        [[ "$expected" -gt 0 ]] || continue

        build_missing_manifest "$year_manifest" "$outdir" "$missing_manifest"

        missing=$(wc -l < "$missing_manifest" | tr -d '[:space:]')
        present=$((expected - missing))

        echo
        echo "[${hemi^^} $year] upstream=$expected  present=$present  missing=$missing"

        if [[ "$missing" -eq 0 ]]; then
            echo "[${hemi^^} $year] already complete; skipping."
            continue
        fi

        if [[ "$DISCOVER_ONLY" == "1" ]]; then
            echo "[${hemi^^} $year] DISCOVER_ONLY: would download $missing files."
            continue
        fi

        echo "[${hemi^^} $year] downloading only missing files ..."

        copernicusmarine get \
            --dataset-id "$dataset_id" \
            "${VERSION_ARGS[@]}" \
            --dataset-part "$DATASET_PART" \
            --file-list "$missing_manifest" \
            --output-directory "$outdir" \
            --no-directories \
            --max-concurrent-requests "$MAX_CONCURRENT" \
            --log-level INFO

        verify_manifest_locally "$missing_manifest" "$outdir" || {
            echo "ERROR: ${hemi^^} $year incomplete after download." >&2
            exit 1
        }

        verify_new_netcdf "$missing_manifest" "$outdir" || exit 1

        echo "[${hemi^^} $year] complete."
    done

    echo
    if [[ "$DISCOVER_ONLY" == "1" ]]; then
        local total missing_total=0 url name
        total=$(wc -l < "$requested" | tr -d '[:space:]')

        while IFS= read -r url; do
            [[ -n "$url" ]] || continue
            name="${url##*/}"
            [[ -s "$outdir/$name" ]] || missing_total=$((missing_total + 1))
        done < "$requested"

        echo "[${hemi^^}] requested upstream files=$total; missing locally=$missing_total"
    else
        verify_manifest_locally "$requested" "$outdir" || {
            echo "ERROR: final ${hemi^^} verification failed." >&2
            exit 1
        }
        echo "[${hemi^^}] all upstream files in the requested range are present locally."
    fi
}

if [[ "$HEMISPHERE" == "nh" || "$HEMISPHERE" == "both" ]]; then
    process_hemisphere "nh" "$NH_ID" "$NH_DIR"
fi

if [[ "$HEMISPHERE" == "sh" || "$HEMISPHERE" == "both" ]]; then
    process_hemisphere "sh" "$SH_ID" "$SH_DIR"
fi

echo
echo "============================================================"
if [[ "$DISCOVER_ONLY" == "1" ]]; then
    echo "OSI-438 discovery/status check finished."
else
    echo "OSI-438 incremental download finished."
fi
echo "============================================================"
echo "Existing non-empty local files were skipped."
echo "No files are synthesized for dates missing upstream."


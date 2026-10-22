i#!/usr/bin/env bash
#
# Download GIOMAS monthly sea-ice thickness annual binary files
# for 1979-2025 from the Polar Science Center.
#
# Usage:
#   bash download_giomas_heff.sh [DESTINATION]
#
# Example:
#   bash download_giomas_heff.sh \
#       ../../../GIOMAS/heff/gz_from_site/binary
#
# Original location where the dowload script was (same for piomas download script):
#   /pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/PSC/scripts
#
# Current PSC packaging differs by year:
#   - older years are distributed as heff.HYYYY.gz
#   - recent years (currently 2024-2025) are distributed as raw
#     heff.HYYYY binaries
#
# This script handles both automatically and ALWAYS leaves the local files as
# heff.HYYYY.gz, which is the format expected by
# process_sithick_binary_Giomas.py.
#
# Validation:
#   GIOMAS monthly thickness = 12 x 276 x 360 float32 values/year
#   Expected uncompressed bytes = 12 * 276 * 360 * 4 = 4,769,280 bytes.
#

set -euo pipefail

BASE_URL="https://pscfiles.apl.washington.edu/zhang/Global_seaice"
START_YEAR=1979
END_YEAR=2025

NX=360
NY=276
NT=12
FLOAT_BYTES=4
EXPECTED_BYTES=$((NT * NY * NX * FLOAT_BYTES))

DEST="${1:-./GIOMAS_heff_binary}"
mkdir -p "${DEST}"

cleanup_tmp () {
    rm -f "${DEST}"/.heff_download_*.raw \
          "${DEST}"/.heff_download_*.gz
}
trap cleanup_tmp EXIT

validate_gzip () {
    local file="$1"

    gzip -t "${file}" 2>/dev/null || return 1

    local nbytes
    nbytes=$(gzip -cd "${file}" | wc -c | tr -d '[:space:]')

    [[ "${nbytes}" -eq "${EXPECTED_BYTES}" ]]
}

validate_raw () {
    local file="$1"
    local nbytes
    nbytes=$(wc -c < "${file}" | tr -d '[:space:]')

    [[ "${nbytes}" -eq "${EXPECTED_BYTES}" ]]
}

curl_common=(
    --fail
    --location
    --retry 5
    --retry-delay 2
    --connect-timeout 30
    --silent
    --show-error
)

echo "GIOMAS annual sea-ice thickness download"
echo "Years       : ${START_YEAR}-${END_YEAR}"
echo "Destination : ${DEST}"
echo "Grid        : ${NX} x ${NY}"
echo "Months/year : ${NT}"
echo "Expected uncompressed size/year: ${EXPECTED_BYTES} bytes"
echo
echo "Local output is normalized to heff.HYYYY.gz for all years."
echo

for year in $(seq "${START_YEAR}" "${END_YEAR}"); do
    gz_name="heff.H${year}.gz"
    raw_name="heff.H${year}"

    outfile="${DEST}/${gz_name}"

    if [[ -f "${outfile}" ]] && validate_gzip "${outfile}"; then
        echo "[OK]       ${gz_name} already present and valid"
        continue
    fi

    if [[ -f "${outfile}" ]]; then
        echo "[INVALID]  ${gz_name}; removing and downloading again"
        rm -f "${outfile}"
    fi

    tmp_gz="${DEST}/.heff_download_${year}.gz"
    tmp_raw="${DEST}/.heff_download_${year}.raw"
    rm -f "${tmp_gz}" "${tmp_raw}"

    # Prefer the historical compressed binary if PSC provides it.
    gz_url="${BASE_URL}/${gz_name}"

    if curl "${curl_common[@]}" --output "${tmp_gz}" "${gz_url}" 2>/dev/null; then
        if validate_gzip "${tmp_gz}"; then
            mv "${tmp_gz}" "${outfile}"
            echo "[OK:gzip] ${gz_name}"
            continue
        fi

        echo "ERROR: PSC returned ${gz_name}, but it failed validation." >&2
        rm -f "${tmp_gz}"
        exit 1
    fi

    rm -f "${tmp_gz}"

    # If no .gz exists, try the recent uncompressed PSC binary.
    raw_url="${BASE_URL}/${raw_name}"
    echo "[RAW]      ${raw_name} (.gz not available; downloading raw binary)"

    if ! curl "${curl_common[@]}" --output "${tmp_raw}" "${raw_url}"; then
        echo "ERROR: neither ${gz_name} nor ${raw_name} could be downloaded." >&2
        rm -f "${tmp_raw}"
        exit 1
    fi

    if ! validate_raw "${tmp_raw}"; then
        nbytes=$(wc -c < "${tmp_raw}" | tr -d '[:space:]')
        echo "ERROR: ${raw_name} has ${nbytes} bytes; expected ${EXPECTED_BYTES}." >&2
        rm -f "${tmp_raw}"
        exit 1
    fi

    # Normalize to the .gz layout required by the existing Climate-DT script.
    gzip -c "${tmp_raw}" > "${tmp_gz}"

    if ! validate_gzip "${tmp_gz}"; then
        echo "ERROR: locally compressed ${gz_name} failed validation." >&2
        rm -f "${tmp_raw}" "${tmp_gz}"
        exit 1
    fi

    mv "${tmp_gz}" "${outfile}"
    rm -f "${tmp_raw}"

    echo "[OK:raw->gz] ${gz_name}"
done

echo
echo "All GIOMAS thickness files ${START_YEAR}-${END_YEAR} downloaded and validated."

count=$(find "${DEST}" -maxdepth 1 -type f -name 'heff.H????.gz' | wc -l | tr -d '[:space:]')
echo "Canonical annual files found: ${count}"

if [[ "${count}" -ne $((END_YEAR - START_YEAR + 1)) ]]; then
    echo "WARNING: expected $((END_YEAR - START_YEAR + 1)) annual files." >&2
fi

echo
echo "First/last files:"
ls -lh "${DEST}/heff.H${START_YEAR}.gz" \
       "${DEST}/heff.H${END_YEAR}.gz"

echo
echo "Next step:"
echo "  Set yeare = ${END_YEAR} in process_sithick_binary_Giomas.py"
echo "  and point sourcedir to:"
echo "  ${DEST}"


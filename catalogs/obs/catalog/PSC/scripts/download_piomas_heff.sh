#!/usr/bin/env bash
#
# Download PIOMAS v2.1 monthly sea-ice thickness annual binary files
# for 1979-2025 from the Polar Science Center.
#
# Usage:
#   bash download_piomas_heff.sh [DESTINATION]
#
# Example:
#   bash download_piomas_heff.sh ../../../PIOMAS/heff/gz_from_site/binary
#
# The script:
#   - downloads only heff.HYYYY.gz (not the PSC NetCDF/text products)
#   - resumes/skips valid files already present
#   - checks gzip integrity
#   - checks the uncompressed binary size expected for
#       12 months x 120 x 360 x 4-byte floats = 2,073,600 bytes
#

set -euo pipefail

BASE_URL="https://pscfiles.apl.washington.edu/zhang/PIOMAS/data/v2.1/heff"
START_YEAR=1979
END_YEAR=2025
EXPECTED_BYTES=$((12 * 120 * 360 * 4))

DEST="${1:-./PIOMAS_heff_binary}"
mkdir -p "${DEST}"

echo "PIOMAS v2.1 annual sea-ice thickness download"
echo "Years       : ${START_YEAR}-${END_YEAR}"
echo "Destination : ${DEST}"
echo "Expected uncompressed size per annual file: ${EXPECTED_BYTES} bytes"
echo

validate_file () {
    local file="$1"

    # gzip integrity
    if ! gzip -t "${file}" 2>/dev/null; then
        return 1
    fi

    # Expected annual binary size
    local nbytes
    nbytes=$(gzip -cd "${file}" | wc -c | tr -d '[:space:]')

    [[ "${nbytes}" -eq "${EXPECTED_BYTES}" ]]
}

for year in $(seq "${START_YEAR}" "${END_YEAR}"); do
    name="heff.H${year}.gz"
    url="${BASE_URL}/${name}"
    outfile="${DEST}/${name}"

    if [[ -f "${outfile}" ]] && validate_file "${outfile}"; then
        echo "[OK]       ${name} already present and valid"
        continue
    fi

    if [[ -f "${outfile}" ]]; then
        echo "[INVALID]  ${name}; removing and downloading again"
        rm -f "${outfile}"
    else
        echo "[DOWNLOAD] ${name}"
    fi

    tmp="${outfile}.part"
    rm -f "${tmp}"

    curl \
        --fail \
        --location \
        --retry 5 \
        --retry-delay 2 \
        --connect-timeout 30 \
        --output "${tmp}" \
        "${url}"

    mv "${tmp}" "${outfile}"

    if ! validate_file "${outfile}"; then
        echo "ERROR: ${name} failed gzip or binary-size validation." >&2
        rm -f "${outfile}"
        exit 1
    fi

    echo "[OK]       ${name}"
done

echo
echo "All PIOMAS files ${START_YEAR}-${END_YEAR} downloaded and validated."
echo "File count:"
find "${DEST}" -maxdepth 1 -type f -name 'heff.H????.gz' | wc -l

echo
echo "First/last files:"
ls -lh "${DEST}/heff.H${START_YEAR}.gz" "${DEST}/heff.H${END_YEAR}.gz"


set -euo pipefail

HEMI="${1:-}"
if [[ "$HEMI" != "nh" && "$HEMI" != "sh" ]]; then
  echo "Usage: $0 nh|sh" >&2
  exit 2
fi

START_YEAR="${START_YEAR:-2021}"
END_YEAR="${END_YEAR:-$(date +%Y)}"
OUTDIR="${OUTDIR:-osi-430a-$HEMI}"

BASE_CAT="https://thredds.met.no/thredds/catalog/osisaf/met.no/reprocessed/ice/conc_cra_files"
BASE_FS="https://thredds.met.no/thredds/fileServer"

mkdir -p "url_lists" "$OUTDIR"

# Step 1: build URL lists
for Y in $(seq "$START_YEAR" "$END_YEAR"); do
  LIST_FILE="url_lists/${HEMI}_${Y}.txt"
  : > "$LIST_FILE"  # empty/overwrite
  for M in $(seq -w 01 12); do
    cat_url="$BASE_CAT/$Y/$M/catalog.xml"
    echo "Indexing $Y-$M"
    # -f: fail on HTTP errors; -sS: silent but show errors; || continue if missing
    xml=$(curl -fsS "$cat_url") || continue
    echo "$xml" \
      | grep 'urlPath="' \
      | grep "ice_conc_${HEMI}_" \
      | sed -E "s@.*urlPath=\"([^\"]+)\".*@$BASE_FS/\1@" \
      >> "$LIST_FILE"
  done
done

# Step 2: download from lists
for f in url_lists/${HEMI}_*.txt; do
  echo "Downloading from $f"
  wget -c -i "$f" \
    --tries=3 --timeout=30 --waitretry=5 --wait=1 --random-wait \
    -P "$OUTDIR"
done

echo "Done. Files saved under: $OUTDIR/"

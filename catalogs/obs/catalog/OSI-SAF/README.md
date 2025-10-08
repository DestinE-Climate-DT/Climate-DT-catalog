# Description of the data

In our `obs` catalog for `OSI-SAF`, the sea-ice concentration Climate Data Record (CDR) for both the Northern and Southern Hemispheres is obtained by combining two complementary datasets, ensuring a continuous and homogeneous time series from 1978 to 2024. In our catalog, only complete years were included; therefore, 2025 was excluded.

> By concatenating OSI-450-a1 (1978–2020) and OSI-430-a (2021–2024), we obtain a continuous, homogeneous sea-ice dataset spanning 1978–2024.

More info about the two datasets [Global Sea Ice Concentration CDR](https://osisaf-hl.met.no/osi-450a1-430a-desc)

## 1. OSI-450-a1 (Climate Data Record (CDR))

- Latest full series temporal coverage: **1978–2020**, released in 2025.  
We used the latest available release (`v3.1`, September 2025), in which corrections were applied to 343 days across the 40-year span, mostly affecting coastal regions.

The product is provided on a 25 km EASE2 grid, with per-grid-cell uncertainty estimates included.

This dataset is derived from passive microwave sensors (SMMR, SSM/I, SSMIS) and processed as L3+L4 products providing daily averages. We post-processed the data into monthly means.

## 2. OSI-430-a1 (Interim CDR, ICDR)

- Associated with the Climate Data Record OSI-450-a1 and fully consistent with it, ensuring homogeneity.  
Temporal coverage: **2021-onwards**.

The same processing chain as OSI-450-a1 was applied, ensuring consistency in algorithms and calibration across the transition.

It likewise provides L3+L4 daily files, from which we derived monthly averages.

## Differences of new version (v3.1) against previous version (v2)

As mentianed above, it is important to highlight that a newer version of the dataset is used respect to the old one (v2.0).
Some of the different approach across multiple stages of the data processing are mentioned here:

- the old data v2.0:  
uses Fundamental Climate Data Record (FCDR) version V003 (see [LINK](https://osisaf-hl.met.no/osi-450a1-430a-desc))
using _ERA-Interim_ data which is the base for the Climate Data Record (CDR) used for seaice concentration siconc.

- the new data v3.1:  
are based on FCDR V004 (so different full reprocessing), using _ERA5_ data as input for OSI FAS CDR version for siconc.

The Product User Manual for OSI-450-a1 v3.1 states:

In v3, the **binary land mask (smask)**:  
“_The binary smask is tuned to closely match that of the NSIDC sea-ice concentration (SIC) CDR … this corresponds to setting all 25×25 km grid cells with a fraction of land lower than 30% to water (ocean or lake)._”

where the **land spill-over correction**, is a filters applied in the OSI SAF SIC CDR and directly affects how many pixels end up masked or set to zero:  
"_was improved for the v3 SIC CDR … validation confirmed less land spill-over effects in v3 than in v2._”

Another thing that worth to be considered is that the spatial interpolation scheme in v3 has changed, which implies a different data reprocessing.

For further info:  
Product User's Manual for [OSI-450-a1 (v3.1) and OSI-430-a (v3.0)](https://osisaf-hl.met.no/sites/osisaf-hl/files/user_manuals/osisaf_cdop3_ss2_pum_sea-ice-conc-climate-data-record_v3p2.pdf)

# Downloading the OSI-SAF Data: 1978 - 2020 (OSI-450-a1) - latest: v3.1

Link page: https://osi-saf.eumetsat.int/products/osi-450-a1 

In bash terminal, the a data list witht the url need to be created (`url_lists`)
with a directory for the data (`data`)

```text
On the 16th Sep 2025, the maintainer of the data Jinlun Zhang (jlzhang@uw.edu) was emailed by me to check for any 
changes/bugs/updates and he confirmed that the site gives access to all the updated data up to 2024 complete and 
2025 (but incomplete, as we speak) without adding any change.
```

After https://github.com/DestinE-Climate-DT/Climate-DT-catalog/pull/185#issuecomment-3303440314 comment,
it is decided to keep data only up to 2024 (complete years)

Note: To download the data, each step was executed separately.

On LUMI directory: `/pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/OSI-SAF/`

-> created tmp directory.

```bash
# Create dir where to put URL lists and data
mkdir -p url_lists data

# 0) Check existance of URL lists and data on server
curl -I https://thredds.met.no/thredds/catalog/osisaf/met.no/reprocessed/ice/conc_450a1_files/1979/07/catalog.html
```

If the answer is something like:

```bash
HTTP/1.1 200 
Server: nginx 
Date: Tue, 16 Sep 2025 10:30:42 GMT 
Content-Type: text/html;charset=UTF-8 
Content-Length: 15266 
Connection: keep-alive 
Access-Control-Allow-Origin: * 
Strict-Transport-Security: max-age=63072000
```

The `HTTP/1.1 200` response confirms that the catalog for July 1979 exists on the THREDDS server, so the download can proceed.

```bash
# 1) Build URL lists by month (handles missing months gracefully)
for Y in $(seq 1979 2020); do
  : > "url_lists/$Y.txt"  # empty/overwrite
  for M in $(seq -w 01 12); do
    cat_url="https://thredds.met.no/thredds/catalog/osisaf/met.no/reprocessed/ice/conc_450a1_files/$Y/$M/catalog.xml"
    echo "Indexing $Y-$M"
    # -f: fail on HTTP errors; -sS: silent but show errors; || continue if month missing
    xml=$(curl -fsS "$cat_url") || continue
    # extract fileServer URLs for SH daily files
    echo "$xml" \
    | grep 'urlPath="' \
    | grep 'ice_conc_sh_' \
    | sed -E 's/.*urlPath="([^"]+)".*/https:\/\/thredds.met.no\/thredds\/fileServer\/\1/' \
    >> "url_lists/$Y.txt"
  done
done

# 2) Inspect a few lines to confirm
head url_lists/1979.txt
head url_lists/1982.txt

# 3) If the generated name lists in YEAR.txt contain the "NN:https://thredds..." prefixes, clean the NN: in place in `url_lists` with:
find url_lists -type f -name '*.txt' -exec sed -E -i.bak 's#^[[:space:]]*[0-9]+:(https?://)#\1#' {} +

# 4) Create a screen for overnight bulk downloads
screen -S download_data

# 5) Download (resumable retries). Creates year/month dirs from URL paths.
for f in url_lists/*.txt; do
  echo "Downloading from $f"
  wget -c -i "$f" --tries=3 --timeout=30 --waitretry=5 --wait=1 --random-wait -P data
done

# 6) If the data are downloading, detach from screen
Ctrl + A + D
```

### Important info on data

While downloading the updated data 1978i-2020 for OSI-SAF (OSI-450-a1), it seems that
for 1986 the Nimbus-7 SMMR instrument had irregularities from 2 Apr to 23 Jun 1986,
so for these two months:

```bash
Indexing 1986-04
curl: (22) The requested URL returned error: 404
Indexing 1986-05
curl: (22) The requested URL returned error: 404
```

no data are produced. This leads to incomplete data if one wants to include that year for any analysis.

*"... From 2 April 1986 to 23 June 1986, a special operation took place during which SMMR was switched off more frequently ..."*

This gap in the data is found also in the previous version of the data (`v2p0`) and can be seen easily with a `ncdump -h` for year 1986.

[Link to official instrument doc (last access: 15/Sep/2025)](https://nsidc.org/sites/default/files/nsidc-0071-v001-userguide_1.pdf)


### Local data postprocessing at server: concatenation

Using `aqua` environment or another created environment,
the data have been subsequently concatenated using CDO:

```bash
#!/bin/bash

# Double check namefiles!

in_dir="./data"
out_dir="."

# Loop over the years 1979 to 2020; 2021 to 2024
for year in $(seq 1979 2020); do
# for year in $(seq 2021 2024); do
    echo "Processing year $year..."

    # Define output file name
    outfile="${out_dir}/ice_conc_sh_ease2-250_cdr-v3p1_${year}.nc"

    # Apply cdo cat to all matching files
    cdo cat ${in_dir}/ice_conc_sh_ease2-250_cdr-v3p1_${year}*.nc $outfile

    echo " -> Created $outfile"
done
```

# Downloading the OSI-SAF Data: 2021 - 2024 (OSI-430-a) - latest: v3.0

Link page to OSI SAF (Ocean & Sea Ice Satellite Application Facility)   
presenting the OSI-430-a dataset data: https://osi-saf.eumetsat.int/products/osi-430-a 

```bash
# Where to put URL lists and data
mkdir -p url_lists data

# 0) Check existance of where to put URL lists and data
curl -I https://thredds.met.no/thredds/catalog/osisaf/met.no/reprocessed/ice/conc_cra_files/2021/07/catalog.html
```

If `200` then connection to server is ok.

- To download the data I used the following script named `get_osi430a_list.sh`:

```bash
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

# Create dir whete to save the data downloaded
mkdir -p "url_lists" "$OUTDIR"

# Step 1: build URL lists with curl
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
```  

# Local data post-processing at server: data concatenation  

Now we have the daily files, but we want to concatenate them by year. We will use CDO for this.  

- Using `aqua` environment or another created environment, the data have been subsequently concatenated using CDO,
file name `cat_cdo_seaice.sh`:  

```bash
#!/bin/bash

# Hemisphere argument (default: nh)
HEM=${1:-"nh"}

# Directories
in_dir_cdr="./osi-450-a1-${HEM}"  # For osi-450-a1 :: 1979 - 2020 (v3p1)
in_dir_icdr="./osi-430a-${HEM}"   # For osi-430a   :: 2021 - 2024 (v3p0)
out_dir="."

# --- Process CDR years (1979 - 2020, v3p1) ---
for year in $(seq 1979 2020); do
    echo "Processing CDR year $year for hemisphere ${HEM}..."
    outfile="${out_dir}/ice_conc_${HEM}_ease2-250_cdr-v3p1_${year}.nc"
    cdo cat ${in_dir_cdr}/ice_conc_${HEM}_ease2-250_cdr-v3p1_${year}*.nc $outfile
    echo " -> Created $outfile"
done

# --- Process ICDR years (2021 - 2024, v3p0) ---
for year in $(seq 2021 2024); do
    echo "Processing ICDR year $year for hemisphere ${HEM}..."
    outfile="${out_dir}/ice_conc_${HEM}_ease2-250_cdr-v3p0_${year}.nc"
    cdo cat ${in_dir_icdr}/ice_conc_${HEM}_ease2-250_icdr*-v3p0_${year}*.nc $outfile
    echo " -> Created $outfile"
done

echo "All years processed for hemisphere ${HEM}."
```  

## Log merged daily data using `cdo cat` command:  

This log is useful as it allow to double check the number of timesteps that have been merged with CDO.  

### OSI-450-a1 : Northern Hemisphere

```bash
Processing year 1979 for hemisphere nh...  
cdo    cat: Processed 200434176 values from 1074 variables over 179 timesteps [21.19s 456MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1979.nc  
Processing year 1980 for hemisphere nh...  
cdo    cat: Processed 192595968 values from 1032 variables over 172 timesteps [21.56s 452MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1980.nc  
Processing year 1981 for hemisphere nh...  
cdo    cat: Processed 201553920 values from 1080 variables over 180 timesteps [22.26s 457MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1981.nc  
Processing year 1982 for hemisphere nh...  
cdo    cat: Processed 198194688 values from 1062 variables over 177 timesteps [22.89s 456MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1982.nc  
Processing year 1983 for hemisphere nh...  
cdo    cat: Processed 204913152 values from 1098 variables over 183 timesteps [22.20s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1983.nc  
Processing year 1984 for hemisphere nh...  
cdo    cat: Processed 198194688 values from 1062 variables over 177 timesteps [20.91s 455MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1984.nc  
Processing year 1985 for hemisphere nh...  
cdo    cat: Processed 200434176 values from 1074 variables over 179 timesteps [21.98s 456MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1985.nc  
Processing year 1986 for hemisphere nh...  
cdo    cat: Processed 154524672 values from 828 variables over 138 timesteps [15.52s 434MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1986.nc  
Processing year 1987 for hemisphere nh...  
cdo    cat: Processed 257541120 values from 1380 variables over 230 timesteps [27.12s 457MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1987.nc  
Processing year 1988 for hemisphere nh...  
cdo    cat: Processed 387431424 values from 2076 variables over 346 timesteps [41.80s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1988.nc  
Processing year 1989 for hemisphere nh...  
cdo    cat: Processed 403107840 values from 2160 variables over 360 timesteps [43.29s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1989.nc  
Processing year 1990 for hemisphere nh...  
cdo    cat: Processed 393030144 values from 2106 variables over 351 timesteps [40.65s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1990.nc  
Processing year 1991 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [55.29s 443MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1991.nc  
Processing year 1992 for hemisphere nh...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [43.11s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1992.nc  
Processing year 1993 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [43.09s 460MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1993.nc  
Processing year 1994 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [45.17s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1994.nc  
Processing year 1995 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [46.18s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1995.nc  
Processing year 1996 for hemisphere nh...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [44.83s 460MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1996.nc  
Processing year 1997 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [46.42s 460MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1997.nc  
Processing year 1998 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [45.23s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1998.nc  
Processing year 1999 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [43.99s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_1999.nc  
Processing year 2000 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [44.97s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2000.nc  
Processing year 2001 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [46.70s 458MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2001.nc  
Processing year 2002 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [43.32s 460MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2002.nc  
Processing year 2003 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [51.22s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2003.nc  
Processing year 2004 for hemisphere nh...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [41.87s 460MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2004.nc  
 Processing year 2005 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [47.11s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2005.nc  
Processing year 2006 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [48.59s 460MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2006.nc  
Processing year 2007 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [42.99s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2007.nc  
Processing year 2008 for hemisphere nh...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [44.02s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2008.nc  
Processing year 2009 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [62.47s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2009.nc  
Processing year 2010 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [45.05s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2010.nc  
Processing year 2011 for hemisphere nh...  
cdo    cat: Processed 407586816 values from 2184 variables over 364 timesteps [42.76s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2011.nc  
Processing year 2012 for hemisphere nh...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [56.51s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2012.nc  
Processing year 2013 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [46.07s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2013.nc  
Processing year 2014 for hemisphere nh...
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [47.85s 459MB]
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2014.nc
Processing year 2015 for hemisphere nh...
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [44.83s 459MB]
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2015.nc
Processing year 2016 for hemisphere nh...
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [43.35s 459MB]
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2016.nc
Processing year 2017 for hemisphere nh...
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [45.05s 459MB]
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2017.nc
Processing year 2018 for hemisphere nh...
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [46.14s 459MB]
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2018.nc
Processing year 2019 for hemisphere nh...
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [45.53s 458MB]
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2019.nc
Processing year 2020 for hemisphere nh...
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [43.90s 460MB]
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p1_2020.nc
```

### OSI-430-a : Northern Hemisphere

```bash
Processing year 2021 for hemisphere nh...  
cdo    cat: Processed 407586816 values from 2184 variables over 364 timesteps [44.27s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p0_2021.nc  
Processing year 2022 for hemisphere nh...  
cdo    cat: Processed 407586816 values from 2184 variables over 364 timesteps [42.80s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p0_2022.nc  
Processing year 2023 for hemisphere nh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [43.04s 460MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p0_2023.nc  
Processing year 2024 for hemisphere nh...  
cdo    cat: Processed 403107840 values from 2160 variables over 360 timesteps [42.13s 459MB]  
 -> Created ./ice_conc_nh_ease2-250_cdr-v3p0_2024.nc  
```

### OSI-450-a1 : Southern Hemisphere  

```bash
Processing year 1979...  
cdo    cat: Processed 200434176 values from 1074 variables over 179 timesteps [15.29s 457MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1979.nc  
Processing year 1980...  
cdo    cat: Processed 192595968 values from 1032 variables over 172 timesteps [14.72s 454MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1980.nc  
Processing year 1981...  
cdo    cat: Processed 201553920 values from 1080 variables over 180 timesteps [15.25s 458MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1981.nc  
Processing year 1982...  
cdo    cat: Processed 198194688 values from 1062 variables over 177 timesteps [19.85s 456MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1982.nc  
Processing year 1983...  
cdo    cat: Processed 204913152 values from 1098 variables over 183 timesteps [20.82s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1983.nc   
Processing year 1984...   
cdo    cat: Processed 198194688 values from 1062 variables over 177 timesteps [20.30s 456MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1984.nc  
Processing year 1985...  
cdo    cat: Processed 200434176 values from 1074 variables over 179 timesteps [20.63s 457MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1985.nc  
Processing year 1986...  
cdo    cat: Processed 154524672 values from 828 variables over 138 timesteps [16.08s 433MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1986.nc  
Processing year 1987...  
cdo    cat: Processed 257541120 values from 1380 variables over 230 timesteps [26.53s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1987.nc  
Processing year 1988...  
cdo    cat: Processed 387431424 values from 2076 variables over 346 timesteps [39.28s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1988.nc  
Processing year 1989...  
cdo    cat: Processed 403107840 values from 2160 variables over 360 timesteps [41.31s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1989.nc  
Processing year 1990...  
cdo    cat: Processed 394149888 values from 2112 variables over 352 timesteps [39.93s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1990.nc  
Processing year 1991...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.57s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1991.nc  
Processing year 1992...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [41.74s 458MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1992.nc  
Processing year 1993...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.61s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1993.nc  
Processing year 1994...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.32s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1994.nc  
Processing year 1995...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.67s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1995.nc  
Processing year 1996...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [41.72s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1996.nc  
Processing year 1997...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [42.09s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1997.nc  
Processing year 1998...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.65s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1998.nc  
Processing year 1999...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.87s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_1999.nc  
Processing year 2000...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [42.19s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2000.nc  
Processing year 2001...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [42.61s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2001.nc  
Processing year 2002...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.87s 457MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2002.nc  
Processing year 2003...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.38s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2003.nc  
Processing year 2004...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [41.67s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2004.nc  
Processing year 2005...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [42.68s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2005.nc  
Processing year 2006...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [42.19s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2006.nc  
Processing year 2007...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.89s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2007.nc  
Processing year 2008...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [48.65s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2008.nc  
Processing year 2009...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.61s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2009.nc  
Processing year 2010...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [42.73s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2010.nc  
Processing year 2011...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [42.19s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2011.nc  
Processing year 2012...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [42.46s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2012.nc  
Processing year 2013...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [40.96s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2013.nc  
Processing year 2014...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [40.76s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2014.nc  
Processing year 2015...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.30s 458MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2015.nc  
Processing year 2016...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [41.12s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2016.nc  
Processing year 2017...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.78s 457MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2017.nc  
Processing year 2018...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.55s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2018.nc  
Processing year 2019...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [41.67s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2019.nc  
Processing year 2020...  
cdo    cat: Processed 409826304 values from 2196 variables over 366 timesteps [41.48s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p1_2020.nc  
```

### OSI-430-a : Southern Hemisphere

```bash
Processing year 2021 for hemisphere sh...  
cdo    cat: Processed 407586816 values from 2184 variables over 364 timesteps [41.87s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p0_2021.nc  
Processing year 2022 for hemisphere sh...  
cdo    cat: Processed 407586816 values from 2184 variables over 364 timesteps [44.25s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p0_2022.nc  
Processing year 2023 for hemisphere sh...  
cdo    cat: Processed 408706560 values from 2190 variables over 365 timesteps [43.18s 460MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p0_2023.nc  
Processing year 2024 for hemisphere sh...  
cdo    cat: Processed 403107840 values from 2160 variables over 360 timesteps [41.87s 459MB]  
 -> Created ./ice_conc_sh_ease2-250_cdr-v3p0_2024.nc
```

Finally, the data are concatenated:

```bash
cdo cat file1.nc file2.nc ... cat_nh.nc
cdo cat file1.nc file2.nc ... cat_sh.nc
```

then time-sorted and monthly averaged using `cdo monmean`

```bash
# mergetime sort in time the data into one single file
cdo mergetime ice_conc_nh*.nc merged_nh.nc
# then monthly mean the resulting data 
cdo monmean merged_nh.nc ice_conc_nh_ease2-250_cdr-v3_1978-2024.nc

# mergetime sort in time the data into one single file
cdo mergetime ice_conc_sh*.nc merged_sh.nc
# then monthly mean the resulting data 
cdo monmean merged_sh.nc ice_conc_sh_ease2-250_cdr-v3_1978-2024.nc
```
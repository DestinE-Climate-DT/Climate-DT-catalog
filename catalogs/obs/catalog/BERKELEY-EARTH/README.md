## Berkeley Earth data

### Available sources

The `aqua-filled` experiment provides monthly surface temperature (`2t`, in degC) from Berkeley Earth, gap-filled for AQUA usage. The `r100-monthly` and `r025-monthly` sources also provide the monthly means of the daily maximum (`max_2t`) and minimum (`min_2t`) temperature, which are available over land only:

| Source | Resolution | Period | Berkeley Earth product | Notes |
|---|---|---|---|---|
| `r100-monthly` | 1x1 deg | 1979-2025 | `Global_TAVG_Gridded_1deg.nc`, `Land_TMAX_Gridded_1deg.nc`, `Land_TMIN_Gridded_1deg.nc` | Beta product (new dataset) |
| `r025-monthly` | 0.25x0.25 deg | 1979-2025 | `Global_TAVG_Gridded_0p25deg.nc`, `Land_TMAX_Gridded_0p25deg.nc`, `Land_TMIN_Gridded_0p25deg.nc` | Beta product at high resolution (new dataset) |
| `r100-monthly-v1` | 1x1 deg | 1979-2024 | `Land_and_Ocean_LatLong1.nc` | Older version, kept for reproducibility |

The `original` experiment provides the same variable over the full record (1850-2026), as published by Berkeley Earth, **without gap filling** (missing values are kept, in particular in the early years). It is produced with [aqua-obs](https://github.com/AQUA-friends/aqua-obs) (not with `scripts/retrieve_process.py`) and its sources use the `lon-lat-skipna` grid, so that the time-varying missing values are handled when regridding (needs an AQUA version that provides it):

| Source | Resolution | Period | Berkeley Earth product |
|---|---|---|---|
| `r100-monthly` | 1x1 deg | 1850-2026 | `Global_TAVG_Gridded_1deg.nc` |
| `r025-monthly` | 0.25x0.25 deg | 1850-2026 | `Global_TAVG_Gridded_0p25deg.nc` |

Original data are available from the Berkeley Earth data page: https://berkeleyearth.org/data/

### Data Processing Overview

The `scripts/retrieve_process.py` script transforms raw Berkeley Earth global land-ocean temperature data into a gap-filled, analysis-ready AQUA-compatible dataset. The same processing is applied to all three products.

Berkeley Earth provides global temperature data as monthly anomalies relative to a climatological baseline, stored alongside monthly climatological averages. The processing pipeline first reconstructs absolute temperatures by adding these anomalies to their corresponding monthly climatology. Since the original time axis uses decimal years (e.g., 1850.042 for mid-January 1850), we convert this to standard monthly timestamps starting on the first of each month.

To focus on the modern climate period, the dataset is trimmed to include only data from 1979 onwards, which also reduces the issues with missing values. Finally, remaining data gaps are filled using CDO's fillmiss (based on bilinear interpolation) which estimates missing values from neighboring grid points.

The result is a complete monthly temperature dataset spanning 1979 to present for surface temperature, suitable for climate analysis within AQUA without the complications of missing data or format inconsistencies.

The script can also process the monthly means of the daily maximum (`tmax`) and minimum (`tmin`) temperature, which Berkeley Earth publishes as land-only products (`Land_TMAX_Gridded_*.nc`, `Land_TMIN_Gridded_*.nc`) for the new dataset (`v2` and `v2-highres`). The processing is the same, but only the gaps over land are filled: the ocean is kept missing. The variables are saved as `max_2t` and `min_2t`. Since these two variables are missing over the ocean while `2t` is global, the `r100-monthly` and `r025-monthly` sources use the `lon-lat-skipna` grid, so that the missing values are handled when regridding (needs an AQUA version that provides it).

### Usage

The product is selected with the `-v/--version` option (`v1`, `v2` or `v2-highres`, default `v2`):

```bash
# Download and process the new 1x1 deg product
python scripts/retrieve_process.py $DVC_PATH/BERKELEY-EARTH/aqua-filled --download -v v2

# Download and process the new 0.25x0.25 deg product
python scripts/retrieve_process.py $DVC_PATH/BERKELEY-EARTH/aqua-filled --download -v v2-highres
```

The variable is selected with the `--variable` option (`tavg`, `tmax` or `tmin`, default `tavg`):

```bash
# Download and process the maximum temperature of the new 0.25x0.25 deg product
python scripts/retrieve_process.py $DVC_PATH/BERKELEY-EARTH/aqua-filled --download -v v2-highres --variable tmax
```

The last year to keep can be set with the `--end-year` option (default: all the available data); the catalog sources use `--end-year 2025` for all the variables, so that they share the same time axis.

The output file carries the variable in its name, e.g. `Berkeley-Earth_aqua-filled_tmax_0.25x0.25_1979-2025.nc`.

`$DVC_PATH` is the machine-specific data path defined in `catalogs/obs/machine.yaml`; `BERKELEY-EARTH/aqua-filled` is the directory where the catalog expects the files.
## Berkeley Earth data

### Available sources

The `aqua-filled` experiment provides monthly surface temperature (`2t`, in degC) from Berkeley Earth, gap-filled for AQUA usage:

| Source | Resolution | Period | Berkeley Earth product | Notes |
|---|---|---|---|---|
| `r100-monthly` | 1x1 deg | 1979-2025 | `Global_TAVG_Gridded_1deg.nc` | Beta product (new dataset) |
| `r025-monthly` | 0.25x0.25 deg | 1979-2025 | `Global_TAVG_Gridded_0p25deg.nc` | Beta product at high resolution (new dataset) |
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

### Usage

The product is selected with the `-v/--version` option (`v1`, `v2` or `v2-highres`, default `v2`):

```bash
# Download and process the new 1x1 deg product
python scripts/retrieve_process.py $DVC_PATH/BERKELEY-EARTH/aqua-filled --download -v v2

# Download and process the new 0.25x0.25 deg product
python scripts/retrieve_process.py $DVC_PATH/BERKELEY-EARTH/aqua-filled --download -v v2-highres
```

`$DVC_PATH` is the machine-specific data path defined in `catalogs/obs/machine.yaml`; `BERKELEY-EARTH/aqua-filled` is the directory where the catalog expects the files.
# AIMIP catalog

Catalog of the AIMIP (AI Model Intercomparison Project) archive available on Levante in
`/work/ab0995/a270088/AIMIP/minio_copy/ai-mip`: AMIP-style simulations of AI climate models,
one physical model and the reference datasets distributed with them.

## Models and experiments

| Model | Experiments | Members | Grid | Frequencies |
|-------|-------------|---------|------|-------------|
| `ACE2-1-ERA5` | `aimip`, `aimip-p2k`, `aimip-p4k` | 5 | 1 degree Gaussian | monthly, daily |
| `ArchesWeather-V2` | `aimip`, `aimip-p2k`, `aimip-p4k` | 5 (4 for `aimip-p4k`) | 1 degree, poles included | monthly, daily |
| `ArchesWeatherGen-V2` | `aimip`, `aimip-p2k`, `aimip-p4k` | 5 | 1 degree, poles included | monthly, daily |
| `DLESyM` | `aimip`, `aimip-p2k`, `aimip-p4k` | 5 | HEALPix nside=64, by face | monthly, daily |
| `NeuralGCM` | `aimip`, `aimip-p2k`, `aimip-p4k` | 5 | TL63 Gaussian (2.8 degrees) | monthly, daily |
| `NeuralGCM-HRD` | `aimip`, `aimip-p2k`, `aimip-p4k` | 5 | 1 degree | monthly, daily |
| `cBottle-1-3` | `aimip`, `aimip-p2k`, `aimip-p4k` | 5 (1 for `p2k` and `p4k`) | HEALPix nside=64, ring | monthly, daily |
| `MD-1p5` | `aimip`, `aimip-p2k`, `aimip-p4k` | 5 | 1 degree | monthly |
| `MPI-ESM1-2-LR` | `amip` | 1 | 1 degree and T63 Gaussian | monthly |
| `ERA5` | `era5` | | 1 degree and 0.25 degree | monthly |
| `GPCP-SG` | `v2.3` | | 1 degree | monthly |

The `aimip` experiment is forced by observed SST and sea ice from October 1978 to December 2024;
`aimip-p2k` and `aimip-p4k` add a uniform 2 K and 4 K SST increase. Daily data cover only
October 1978 to December 1979 and the year 2024 (DLESyM: October 1978 to December 1984).

## Sources

Every model has the same source names: `monthly-atm2d`, `monthly-atm3d`, `daily-atm2d` and `daily-atm3d`.
When a model provides both the native (`gn`) and the regridded (`gr`) data, the regridded ones are the
default and the native ones have the `-native` suffix (for `ACE2-1-ERA5` these are the 8 native model
layers instead of pressure levels).

Ensemble members are selected with the `realization` parameter, which takes the full variant label:

```python
from aqua import Reader
reader = Reader(catalog="aimip", model="NeuralGCM", exp="aimip", source="monthly-atm2d", realization="r3i1p1f1")
data = reader.retrieve(var="tas")
```

The members of `cBottle-1-3` differ by physics index (`r1i1p1f1` to `r1i1p5f1`); its `aimip-p2k` and
`aimip-p4k` experiments have only `r1i1p4f1`.

## Things to know

- No dedicated fixer exists yet: variables are renamed by the AQUA eccodes convention only (`tas` to `2t`,
  `pr` to `tprate`, `ta` to `t`, ...). `huss`, `tdas`, `zg`, `rlut` and `rsut` keep their CMOR names.
- **Missing values on some pressure levels of the `atm3d` sources.** Each variable is a separate file and
  not all the variables of a model are on the same pressure levels. The `atm3d` sources put them on the
  union of the levels, so a variable is filled with missing values on the levels it does not have, without
  any warning. Select the levels which exist, e.g. `data.zg.sel(plev=50000)`:
  - `MD-1p5` and `MPI-ESM1-2-LR`: `zg` only at 500 hPa, the other variables on 7 levels;
  - `DLESyM`: `ta` only at 850 hPa, `zg` only at 250, 500 and 1000 hPa.

  The other models have all their 3D variables on the same levels. `zg` of the ArchesWeather models has no
  vertical dimension and is in the `atm2d` sources; `zg` of `ERA5` is on 37 levels and has its own source,
  `monthly-atm3d-zg`.
- `DLESyM` has no AQUA grid (`source_grid_name: false`): data can be read but not regridded or averaged.
- 36 files of `NeuralGCM` and `NeuralGCM-HRD` (mostly daily 3D data) are truncated in the archive and
  cannot be opened. They are left out: the affected members miss that variable or period.
- The 0.25 degree ERA5 sources (`monthly-r025-atm2d`, `monthly-r025-atm3d`) have no fixer: check the units
  of the fluxes before using them.
- Superseded version folders are not used. The `ArchesWeatherGen-V2/aimip-era5` folder is not included.

## Updating the catalog

The files under `catalog/` and `catalog.yaml` are generated from the content of the archive, so that
each source points to the current version of each file. After new data are uploaded, run on Levante:

```bash
python scripts/aimip/inventory_aimip.py /work/ab0995/a270088/AIMIP/minio_copy/ai-mip aimip_inventory.json
python scripts/aimip/generate_aimip_catalog.py aimip_inventory.json catalogs/aimip
```

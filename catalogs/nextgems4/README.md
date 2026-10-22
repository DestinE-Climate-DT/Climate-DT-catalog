## NextGEMS 4 Catalog

This catalog contains the NextGEMS cycle4 experiments.
The data are originally available on the Levante HPC, but a transfer to the Lumi HPC is planned.
At the moment, only the AQUA generated LRA for the IFS-FESOM ssp370 experiment is available on Lumi.

Please take a look to this README file for updates on this catalog.
### Status of the sources (checked 2026-10-22)

- **IFS-FESOM `historical-1990` and `ssp370`**: all the Levante paths (FDB, parquet and gribscan references, LRA, pre-computed AQUA analysis) are still available.
- **ICON C5 AMIP runs** (`AMIP_CNTL_R02B07/08/09`, `AMIP_P4K_R02B07/08/09`, `AMPI_4CO2_R02B08`): the data were moved from `/work/mh0730/C5` to `/work/mh1570/C5`.
  The catalog now points to the new location, where the grid files `independent_*` and `atm_vgrid_*` are in the `common` folder and have a `_hpz8` suffix.
- **ICON `ngc4008`**: unchanged, still available.

### Polytope (Data Bridge)

The `IFS-FESOM/historical-1990` experiment is now served only through polytope from the Lumi Data Bridge (class `ng`, generation 1, `bridge_end_date: complete`).
The local FDB sources (`*-fdb1/2/3`) were replaced by the following sources, named as in the `climatedt-gen2` catalog:
`hourly-hpz7-sfc`, `hourly-hpz9-sfc`, `hourly-hpz7-pl`, `hourly-hpz9-pl`, `daily-hpz7-o2d`, `daily-hpz9-o2d`, `daily-hpz7-o3d`, `daily-hpz9-o3d`.
They have been tested with the AQUA Reader (`engine='polytope'`) at the start and at the end of the period.
The data span 1990-01-01 to 2019-12-31 (hourly data end at 23:00, daily data at 00:00).

Notes:
- The sources with the r025 (lat-lon) and native grids had no counterpart on polytope and were removed together with the FDB ones.
- The surface variable 228 (`tp`) was removed from the variable list, since the fixer converts it to `tprate` which is already provided by 260048.
- The ocean 2D variable list is the one of the 2000-2019 period; 263115 (only present in 1990-1999) is not included.
- The hpz9 3D atmospheric source now uses the `hpz9-nested` grid (it was wrongly set to `hpz7-nested`).
- The old local FDB data of the Levante machine are still on disk, but they could not be read with the GSV interface at the time of the check.

The coupled 5km scenario (`ScenarioMIP`, `SSP3-7.0`, generation 1) is **not** available on the Lumi Data Bridge, so `ssp370` still uses the local FDB sources (Levante only) and has not been converted. It could be on the Leonardo Data Bridge, which cannot be accessed yet.

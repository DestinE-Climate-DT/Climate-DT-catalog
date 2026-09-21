# The EN4 datasets

EN4 is an oceanic data set from the Met Office Hadley Centre, documented
[here](https://www.metoffice.gov.uk/hadobs/en4/EN.4.2.2_Product_User_Guide_v1.0.pdf).
Data cover 1950 to 2025. The AQUA ocean diagnostics use:

- Sea water salinity (`so`) and its uncertainty (`so_uncertainty`)
- Sea water potential temperature (`thetao`) and its uncertainty (`thetao_uncertainty`)

Variable names follow the CMOR standard. Two sources are available: `monthly` (the default,
a zarr store) and `monthly-netcdf`. **Both must be kept at the same end year**: `monthly` is an
alias of `monthly-zarr`, so updating only the netcdf leaves every diagnostic on the old data.

## Extending the time series

`scripts/EN4_management.sh` downloads a new year from the Met Office, extracts `so` and `thetao`
with their uncertainties, renames to CMOR, regrids to `EN4_target_grid.txt`, and merges the result
with the existing series. Edit at the top of the script:

```bash
START_YEAR=2026        # year to download
END_YEAR=2026
WORK_DIR=".../datasets-new/en4/download"    # scratch
FINAL_DIR=".../datasets-new/en4"            # staging
```

The previous full series must already be in `FINAL_DIR` (the script merges against it and uses it
as reference for the coordinate check), so copy it there from DVC first.

Only complete years are processed: if a month is missing the whole year is skipped. The download
URL uses the `en4-2-1` directory even for EN.4.2.2 files — that is correct, not a typo.

The script's final merge produces `<var>_EN4_complete_<date>.nc`. For the 2025 extension the
concatenation was instead done explicitly, which is faster and preserves the netcdf4/zip encoding:

```bash
cdo -f nc4 -z zip cat so-EN4-1950-2024.nc so_EN4_2025_2025.nc so-EN4-1950-2025.nc
```

Either way, rename the result to `<var>-EN4-1950-<year>.nc` and check it before going further:

```bash
cdo ntime so-EN4-1950-YYYY.nc          # 12 * number of years
cdo showtimestamp so-EN4-1950-YYYY.nc | tail -1
```

## Regenerating the zarr store

Required at every update, since `monthly` is the zarr. `nc2zarr` is not in the AQUA environment;
on LUMI it is a container-wrapper (see `AQUA/cli/nc2zarr/README.md`):

```bash
export PATH=/pfs/lustrep3/projappl/project_465000454/jvonhar/containers/nc2zarr/bin:$PATH
nc2zarr -vv -c scripts/en4_monthly.yml
```

Update input paths, output store name and end year in `scripts/en4_monthly.yml` first. The run
takes about 7 minutes for the full 1950-2025 series, so a login node is enough — no SLURM needed.
`output.overwrite` is deliberately `false`: a re-run stops instead of clobbering an existing store,
so delete the output directory first if you need to start over.

Chunking must stay `time: 1` with no chunking in space, matching the existing store.

## Publishing

`v4.2.2.dvc` tracks the whole `v4.2.2` directory as a single object, so netcdf and zarr must both
be in place before `dvc add` — otherwise two add/push cycles are needed.

In the working DVC repo (`/pfs/lustrep3/appl/local/climatedt/data/AQUA/aqua-dvc`):

```bash
cd datasets/EN4/v4.2.2
cp <staging>/*-EN4-1950-YYYY.nc netcdf/ && cp netcdf/*-EN4-1950-YYYY.nc .
cp -r <staging>/EN4.v422.1950-YYYY.clev.zarr zarr/
rm netcdf/*-1950-<prev>.nc ./*-1950-<prev>.nc && rm -r zarr/EN4.v422.1950-<prev>.clev.zarr
cd /pfs/lustrep3/appl/local/climatedt/data/AQUA/aqua-dvc
dvc add datasets/EN4/v4.2.2 && dvc push -r ecmwf_climatedt
```

Removing the previous year is safe as long as you have verified that the new netcdf contains it
verbatim (it is a `cdo cat` of the old series plus the new year); the old version stays recoverable
from the DVC cache through the previous `v4.2.2.dvc` in the aqua-dvc git history.

Then commit the new `v4.2.2.dvc` on a branch of `aqua-dvc`, and update `v4.2.2.yaml` here (both
`monthly-zarr` and `monthly-netcdf`).

**The catalog does not read from the working repo.** `machine.yaml` resolves `{{DVC_PATH}}` to a
separate deployment checkout per machine — on LUMI `/pfs/lustrep4/projappl/project_465002727/aqua/aqua-dvc/datasets`
for `lumi`, and `.../input_data/applications/AQUA_O-26.1_v1.0/datasets` for `lumi-o26.1`. Each one
needs `git pull` + `dvc pull` after the push, before this PR is merged, or EN4 breaks there.

## Requirements

`cdo`, `nco` (`ncatted`, `ncrename`, `ncap2`), `wget`, `unzip`, `nc2zarr` (container-wrapper on
LUMI). About 1 GB of scratch per year, 13 GB for the full zarr store.

---------
Last updated by
- Marco Cadau, Politecnico di Torino, Sep 2026
- Marco Cadau, Politecnico di Torino, Oct 2025
- Jost von Hardenberg, PoliTO, Oct 2025

# Observational catalog

This is the catalog containing the observational datasets used in the Climate-DT project.
Each dataset is a different model.

## Why are the data not available?

All the datasets available at least in one machine are present, with paths generalized as possible to check in the machine.yaml file.
This means that there is no automatic check if all the available datasets are deployed in a new machine.
If you have a problem finding data in your machine with these catalog entries, please write in an issue to be sure that the dataset you're looking for is available in your machine.

## Work in progress

- E-OBS v33.0e: only the `monthly-netcdf` source is available. The `daily-netcdf` source is commented because the daily files are not downloaded in aqua-dvc yet.
- E-OBS v33.0e `monthly-netcdf` uses the `eobs-eccodes-monthly` fixer and the eccodes convention for `tg`, `tn`, `tx` (`2t`, `min_2t`, `max_2t`), which require AQUA > v1.2.3.
- GPM `imerg-v07` `monthly`: `precipitation` is translated to `tprate` by the eccodes convention, which requires AQUA > v1.2.3.

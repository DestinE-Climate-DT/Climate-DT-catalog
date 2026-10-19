# aqua-obs: updating the observational datasets

`aqua-obs` is a command line tool for the datasets of the obs catalog. It checks the upstream
sources for new data, then downloads and processes the requested months and writes new products.
Optionally, it also updates the date ranges in the catalog yaml files. Publishing with DVC is
still a manual step.

| dataset    | products                         | upstream                          | modes          |
|------------|----------------------------------|-----------------------------------|----------------|
| `berkeley` | `v2`, `v2-highres` (`v1` frozen) | Berkeley Earth gridded TAVG (GCS) | append, replace |
| `psc`      | `piomas`, `giomas`               | PSC annual `heff` binaries        | append, replace |
| `en4`      | `so`, `thetao`, `zarr`           | Met Office EN.4.2.2 g10 analyses  | append, replace |

The older per-dataset scripts in `catalog/<DATASET>/scripts/` will be removed once each dataset
has been validated here.

## Installation

You need `cdo` and an environment with xarray, netCDF4, zarr, requests and ruamel.yaml. The AQUA
environment already has all of them. Run from this directory:

```bash
python -m aqua_obs --help
```

To use a dedicated environment instead, run from this directory:

```bash
conda env create -f environment.yml   # dependencies + editable install of the tool
conda activate aqua-obs
aqua-obs --help
```

## Configuration

Paths are resolved in this order; the first one found wins:

1. the CLI options `--output-root` and `--workdir`;
2. the `machines:` section of `config.yaml`;
3. the `intake.DVC_PATH` entry of `../machine.yaml`, used as `output_root`.

The machine name comes from the AQUA configuration (`machine: auto`); use `--machine` to override
it. The `workdir` holds downloads, a processing cache, per-dataset state and locks. It can be
large: EN4 needs about 1 GB per year.

Point `output_root` to a staging area or to the aqua-dvc working copy, never to a deployment
checkout. Products are written under new names, and existing files are never modified or
deleted.

The `datasets:` section of `config.yaml` sets, for each dataset:

- `enabled`;
- `products`;
- `start_year`, used as the default start of a replace run;
- `complete_years`: when no `--end` is given, extend only up to the last available December.
  It is on by default for PSC and EN4.

## Local tests (altai)

`config.yaml` has an `altai` entry for the Mac:

- products go to `~/aqua-obs/datasets`;
- downloads and state go to `~/aqua-obs/work`;
- Berkeley processes only `v2`;
- an EN4 replace run starts in 2024.

Because the machine is read from the AQUA config, `aqua-obs` picks this entry up without options.
For a first round trip:

```bash
aqua-obs check
aqua-obs update psc --mode replace --start 202301 --end 202412   # build a small product
aqua-obs check psc                                               # now "new data"
aqua-obs update psc --end 202512 --catalog                       # append and edit the yaml
git diff ../catalog/PSC                                          # inspect, then git checkout
```

Catalog edits, when enabled, go to the repo yaml, so you can review them with `git diff` and
revert them with `git checkout`. To work on a copy instead, set `catalog_root` under
`machines.altai`.

## Usage

```bash
aqua-obs list                                # datasets, modes, products and target paths
aqua-obs check                               # local range vs upstream, nothing downloaded
aqua-obs check psc en4:zarr                  # restrict to datasets or dataset:product
aqua-obs update --dry-run                    # mode and months each product would get
aqua-obs update psc                          # append up to the latest available (complete) year
aqua-obs update en4 --end 202606             # append up to June 2026, error if not available
aqua-obs update psc:giomas --mode replace    # rebuild from the dataset start year
aqua-obs update berkeley --mode replace --start 198001 --end 202412
aqua-obs update en4 --catalog                # also edit the catalog yaml
aqua-obs catalog --dry-run                   # yaml edits matching the files on disk
```

There are two update modes:

- **append**: extends the local product after its last month. `--start` may only be that month
  plus one. Appending to a dataset that does not exist yet is an error.
- **replace**: builds the product from `--start` (default: the dataset start year) to `--end`.
  If a local product exists, it is used as a template for grid, static fields and encoding.

The default is `append` if a local product exists, `replace` otherwise.

`--start` and `--end` take a month as `YYYYMM`, and both bounds are included. Whether either of
them should become mandatory is still open. If upstream does not cover the requested months, the
product fails with an error and nothing is written.

The catalog yaml is edited only when this is enabled, either with `update_catalog: true` in
`config.yaml` (globally or under a machine) or with `--catalog`. `--no-catalog` disables it for a
single run. Without it, `aqua-obs catalog` aligns the yaml with the files on disk at any later time.

For each product, `update` prints:

- the new file;
- the obsolete one;
- the catalog edits;
- a reminder to `dvc add` and `dvc push`, then `git pull` and `dvc pull` on every machine.

The obsolete file can be removed once the new version is in DVC.

### File names

All new products carry the full month range, `<name>_YYYYMM-YYYYMM`. For example:

- `so-EN4-195001-202606.nc`
- `Berkeley-Earth_aqua-filled_1x1_197901-202609.nc`

Existing files named with years (e.g. `so-EN4-1950-2025.nc`) are still recognised as the current
product, so the first update after the switch appends to them. In the catalog, `urlpath` takes
the new `YYYYMM-YYYYMM` range. Descriptions keep the width they already have, so years stay years.

## How it works

`aqua_obs/base.py` defines `ObsDataset`; subclasses register themselves by `name`. A dataset:

- declares its `Product`s, each with:
  - a file name template with `{start}`/`{end}`;
  - a subdirectory of `output_root`;
  - the catalog sources whose range follows it;
- implements three hooks:
  - `remote_info(product)`: what upstream offers, without downloading data (used by `check`);
  - `fetch(product, start, end)`: downloads the raw data of those months;
  - `build(product, raw, start, end, template)`: returns the processed months as an xarray
    Dataset.

The base class handles the rest:

- resolving the mode and the month range;
- selecting the requested months;
- checking that upstream covers them;
- appending, or applying the template;
- writing atomically;
- validating the time axis;
- updating the catalog.

Before anything is written, the suite checks that:

- the variables, dimensions, units and grid match the existing product;
- the new data follow the existing product with no overlap or gap;
- the written file has a continuous monthly time axis (checked again after writing).

When appending:

- netCDF products are rewritten under the new name;
- zarr stores are copied, and the new months are appended to the copy (zarr format 2).

Shared helpers:

| module        | content |
|---------------|---------|
| `fetch.py`    | downloads with retry, `.part` files, resume and validators; HEAD requests; directory listings |
| `io.py`       | append/template checks, atomic netCDF writes, zarr copy and append |
| `catalog.py`  | edits only the range in the `urlpath`/`description` lines of a source |
| `timeaxis.py` | month parsing, selection and checks |
| `cdo.py`      | CDO via subprocess |

### Adding a dataset

1. Create `aqua_obs/datasets/<name>.py` with a subclass of `ObsDataset`:
   - set `name`, `catalog_dir`, `start_year` and `complete_years`;
   - restrict `modes` if needed;
   - implement `all_products()`, `remote_info()`, `fetch()` and `build()`.
2. Import the module in `aqua_obs/datasets/__init__.py`.
3. Add its options to `config.yaml`, and add tests in `tests/`.

## Notes on the datasets

### Berkeley Earth

The processing is the same as in `retrieve_process.py`:

- anomaly plus monthly climatology;
- month-start time axis;
- `2t` in degC;
- `cdo fillmiss` on the selected months.

Upstream is a single file revised every month. `append` adds only the months after the local
end and does not pick up revisions of earlier months; use `replace` to take them.

`check` knows the last upstream month only for the version downloaded last. Otherwise it reports
whether the upstream file changed.

### PSC

Both gzipped and raw yearly binaries are read. The raw file of the current year holds the months
published so far, so `--end` can reach into it.

- When appending, the new months take the curvilinear grid, `areacello`, `sftof` and the time
  bounds layout from the existing `_curvgrid.nc` file.
- Without a local product, the grid comes from the PSC grid files. Check the result against the
  previous product.
- GIOMAS `9999.9` values are set to missing, as `cdo setctomiss` did.

### EN4

The processing is the same as in `EN4_management.sh`:

- CMOR names `so`/`thetao` with their uncertainties;
- `depth` renamed to `lev`;
- no `valid_min`/`valid_max`;
- `cdo remapbil` of each month to `aqua_obs/data/EN4_target_grid.txt`.

The output is identical to the CDO/NCO pipeline. Yearly zips are listed from the EN4 download
page. The zips do not say how many months they hold, so `check` treats the last listed year as
possibly incomplete; extend into it with `--end`.

The processed months are cached in `workdir/en4/processed`; clear the cache to pick up upstream
revisions.

## Tests

```bash
pytest tests          # offline: a local HTTP server stands in for upstream
```

# Local STAC examples for AQUA CI

The `ci` catalog has one `stac` entry that loads `catalog.yaml` in this
directory. It provides collection entries and a nested catalog of items:

- `ifs` and `nemo` point directly to the corresponding STAC collection JSON
  files. Their `source_grid_name` and `fixer_name` metadata are dictionaries
  keyed by item ID.
- `ifs-items` loads `catalog/ifs/main.yaml`. That Intake YAML file describes
  individual IFS item JSON files and gives each item its own metadata. More
  collections can be described under separate `catalog/<collection>/main.yaml`
  paths.

The STAC JSON files are in `tests/stac_catalogue` in the AQUA repository. Their
NetCDF assets are in `AQUA_tests` at the same repository root; CI downloads that
directory separately. Run AQUA from its repository root so the relative paths
in these Intake entries resolve correctly. Neither the JSON nor the NetCDF
files are copied into Climate-DT-catalog.

For example, after installing this catalog as `ci`:

```python
from aqua import Reader

collection_reader = Reader(
    catalog="ci",
    model="stac",
    exp="ifs",
    source="ifs-long-regridded-r18x9",
    areas=False,
)
collection_data = collection_reader.retrieve()

nemo_reader = Reader(
    catalog="ci",
    model="stac",
    exp="nemo",
    source="nemo-eorca1-eorca1-sst-2d",
    areas=False,
)
nemo_data = nemo_reader.retrieve()

item_reader = Reader(
    catalog="ci",
    model="stac",
    exp="ifs-items",
    source="ifs-short-ifs2d-tco79",
    areas=False,
)
item_data = item_reader.retrieve()
```

The collection entry can also be inspected and used directly with Intake:

```python
import aqua  # Registers AQUA's STAC Intake driver.
import intake

catalog = intake.open_catalog("/path/to/Climate-DT-catalog/catalogs/ci/catalog.yaml")
print(list(catalog["stac"]["ifs"]))
data = catalog["stac"]["ifs"]["ifs-short-ifs2d-tco79"]["data"].read()
item_data = catalog["stac"]["ifs-items"]["ifs-short-ifs2d-tco79"].read()
```

# Local STAC examples for AQUA CI

The `ci` catalog has two nested Intake entries for the IFS fixtures in AQUA's
static STAC catalog:

- `stac` loads `catalog/stac/main.yaml`. Its `ifs` entry points to the IFS
  collection, where items can be selected by ID. Item-specific grid and fixer
  metadata live on the collection entry.
- `stac-items` loads `catalog/stac/items/main.yaml`. Its entries point directly
  to individual STAC item JSON files and carry their own metadata, following
  the nested YAML pattern used by the `eerie-cloud` catalog.

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

item_reader = Reader(
    catalog="ci",
    model="stac-items",
    exp="ifs-short-ifs2d-tco79",
    source="data",
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
item_data = catalog["stac-items"]["ifs-short-ifs2d-tco79"]["data"].read()
```


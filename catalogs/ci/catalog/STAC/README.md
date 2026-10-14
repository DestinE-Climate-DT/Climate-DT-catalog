# Local STAC examples for AQUA CI

The `ci` catalog provides two ways to read the IFS fixtures from AQUA's static
STAC catalog:

- `stac-ifs` points to the IFS collection. Its default item is
  `ifs-long-regridded-r18x9`, and another item can be selected at read time.
  The item-specific grid and fixer metadata live on this collection entry.
- `stac-ifs-items` points to `ifs-items.yaml`, which gives each example item
  its own Intake entry and metadata.

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
    model="stac-ifs",
    exp="ifs-long-regridded-r18x9",
    source="data",
    areas=False,
)
collection_data = collection_reader.retrieve()

item_reader = Reader(
    catalog="ci",
    model="stac-ifs-items",
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
print(list(catalog["stac-ifs"]))
data = catalog["stac-ifs"]["ifs-short-ifs2d-tco79"]["data"].read()
```

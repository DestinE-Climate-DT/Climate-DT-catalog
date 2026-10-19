"""Berkeley Earth gridded monthly surface temperature, gaps filled with CDO fillmiss."""

import logging

import numpy as np
import pandas as pd
import xarray as xr

from .. import cdo
from ..base import CatalogEntry, ObsDataset, Product, Remote
from ..fetch import netcdf_opens
from ..timeaxis import select_months

log = logging.getLogger(__name__)

GCS = "https://storage.googleapis.com/berkeley-earth-temperature-hr/global/gridded"
S3 = "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Gridded"
TEMPLATE = "Berkeley-Earth_aqua-filled_{res}x{res}_{{start}}-{{end}}"


def full_field(ds):
    """Absolute temperature = anomaly + monthly climatology, on a month-start time axis."""
    time = ds["time"].values  # decimal years, mid-month
    years = np.floor(time).astype(int)
    months = np.floor((time - years) * 12).astype(int) + 1
    month_index = xr.DataArray(months - 1, dims=["time"])
    out = ds["temperature"] + ds["climatology"].isel(month_number=month_index)
    out = out.assign_coords(time=pd.to_datetime({"year": years, "month": months, "day": 1}).values)
    out = out.drop_vars([c for c in out.coords if c not in out.dims])
    out.name = "2t"
    out.attrs = {"long_name": "Surface Temperature", "units": "degC"}
    return out


class BerkeleyEarth(ObsDataset):
    """A single upstream file per product, revised monthly: append takes the months after the
    local end (earlier months are not revised), replace reprocesses everything."""

    name = "BERKELEY-EARTH"
    description = "Berkeley Earth monthly surface temperature (filled)"
    start_year = 1979

    def all_products(self):
        exp, subdir = "aqua-filled", "BERKELEY-EARTH/aqua-filled"
        return [
            Product(exp, "r100-monthly-v1", TEMPLATE.format(res="1") + "_v1.nc", subdir, frozen=True,
                    params={"url": f"{S3}/Land_and_Ocean_LatLong1.nc"}),
            Product(exp, "r100-monthly", TEMPLATE.format(res="1") + ".nc", subdir,
                    catalog=[CatalogEntry("aqua-filled.yaml", "r100-monthly"),
                             CatalogEntry("main.yaml", "aqua-filled", fields=("description",))],
                    params={"url": f"{GCS}/Global_TAVG_Gridded_1deg.nc"}),
            Product(exp, "r025-monthly", TEMPLATE.format(res="0.25") + ".nc", subdir,
                    catalog=[CatalogEntry("aqua-filled.yaml", "r025-monthly")],
                    params={"url": f"{GCS}/Global_TAVG_Gridded_0p25deg.nc"}),
        ]

    def remote_info(self, product):
        sig = self.fetcher.head(product.params["url"])
        if sig is None:
            return Remote(text="upstream file not found")
        remote = Remote(signature=sig, text=f"modified {sig.get('last_modified')}")
        # the months in the file are known only for the version downloaded last
        last = self.state.get(product.key, "upstream_last")
        if last and self.state.get(product.key, "raw_signature") == sig:
            remote.last = pd.Period(last, freq="M")
            remote.text = f"..{last}, " + remote.text
        return remote

    def fetch_plan(self, product, start, end):
        url = product.params["url"]
        sig = self.fetcher.head(url) or {}
        path = self.workdir / "raw" / url.rsplit("/", 1)[1]
        cached = path.exists() and self.state.get(product.key, "raw_signature") == sig
        size = f"{sig['size'] / 1e6:.0f} MB" if sig.get("size") else "size unknown"
        return [f"{url} ({size}, {'cached in ' + str(path) if cached else 'not cached'})"]

    def fetch(self, product, start, end):
        """The upstream file, downloaded again only if its signature changed."""
        url = product.params["url"]
        path = self.workdir / "raw" / url.rsplit("/", 1)[1]
        sig = self.fetcher.head(url)
        stale = not path.exists() or self.state.get(product.key, "raw_signature") != sig
        self.fetcher.download(url, path, validator=netcdf_opens, overwrite=stale)
        with xr.open_dataset(path) as ds:
            last = str(full_field(ds).time.values[-1])[:7]
        self.state.set(product.key, raw_signature=sig, upstream_last=last)
        return path

    def build(self, product, raw, start, end, template=None):
        with xr.open_dataset(raw) as ds:
            out = select_months(full_field(ds), start, end).load()
        if not out.sizes["time"]:
            return out.to_dataset()
        staging = self.workdir / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        unfilled, filled = staging / f"{product.source}_unfilled.nc", staging / f"{product.source}_filled.nc"
        out.to_netcdf(unfilled)
        filled.unlink(missing_ok=True)
        log.info("Filling missing values with cdo fillmiss")
        cdo.fillmiss(unfilled, filled)
        unfilled.unlink()
        return xr.open_dataset(filled, chunks={})

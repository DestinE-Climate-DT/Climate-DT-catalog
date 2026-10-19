"""Met Office Hadley Centre EN4 objective analyses: salinity and potential temperature."""

import logging
import re
import zipfile
from functools import cached_property
from pathlib import Path

import pandas as pd
import xarray as xr

from .. import cdo
from ..base import CatalogEntry, ObsDataset, Product, Remote
from ..fetch import nonempty

log = logging.getLogger(__name__)

# the en4-2-1 directory holds the EN.4.2.2 files as well: not a typo
DOWNLOAD_ROOT = "https://www.metoffice.gov.uk/hadobs/en4"
TARGET_GRID = Path(__file__).resolve().parents[1] / "data" / "EN4_target_grid.txt"
BOUNDS = ("time_bnds", "depth_bnds")

# original name -> (CMOR name, long_name, standard_name)
VARIABLES = {
    "salinity": ("so", "Sea water salinity", "sea_water_salinity"),
    "temperature": ("thetao", "Potential temperature", "sea_water_potential_temperature"),
}


def cmorize(ds):
    """Select variables and uncertainties, CMOR names, depth -> lev, no valid_min/max.

    Time and depth bounds are kept, as `cdo selvar` did in the original processing."""
    keep = [v for orig in VARIABLES for v in (orig, f"{orig}_uncertainty")]
    missing = [v for v in keep if v not in ds]
    if missing:
        raise KeyError(f"EN4 file lacks {missing}")
    ds = ds[keep + [b for b in BOUNDS if b in ds]]
    rename = {}
    for orig, (name, long_name, standard_name) in VARIABLES.items():
        rename[orig], rename[f"{orig}_uncertainty"] = name, f"{name}_uncertainty"
        ds[orig].attrs.update(long_name=long_name, standard_name=standard_name)
    for var in keep:
        for att in ("valid_min", "valid_max"):
            ds[var].attrs.pop(att, None)
            ds[var].encoding.pop(att, None)
    ds = ds.rename(rename).rename({"depth": "lev"})
    ds["lev"].attrs.update(standard_name="depth", units="m", positive="down")
    return ds


class EN4(ObsDataset):
    name = "EN4"
    description = "EN4.2.2 g10 monthly so/thetao on 1x1 grid"
    start_year = 1950
    complete_years = True

    def all_products(self):
        version = self.options.get("version", "4.2.2")
        exp = f"v{version}"
        # one product, two files with the same months; DVC tracks EN4/v4.2.2 as a whole
        return [Product(exp, "monthly-netcdf", "{file}-EN4-{start}-{end}.nc", f"EN4/{exp}/netcdf",
                        catalog=[CatalogEntry(f"{exp}.yaml", "monthly-netcdf")],
                        files={name: [name, f"{name}_uncertainty"] for name, _, _ in VARIABLES.values()})]

    @cached_property
    def zip_urls(self):
        """{year: url} of the yearly analysis zips listed on the EN4 download page.

        Recent years live in en4-2-1/, older ones in en4-2-1/EN.<version>/."""
        version = self.options.get("version", "4.2.2")
        page = f"{DOWNLOAD_ROOT}/download-en{version.replace('.', '-')}.html"
        v = re.escape(version)
        pattern = rf"(data/en4-2-1/(?:EN\.{v}/)?EN\.{v}\.analyses\.g10\.(\d{{4}})\.zip)"
        return {int(m[2]): f"{DOWNLOAD_ROOT}/{m[1]}" for m in self.fetcher.listing(page, pattern)}

    def remote_info(self, product):
        """The zips do not tell how many months they hold: the last listed year is reported as
        possibly incomplete, and the previous one is taken as complete."""
        years = sorted(self.zip_urls)
        if not years:
            return Remote(text="nothing listed")
        return Remote(last=pd.Period(f"{years[-1] - 1}-12", freq="M"), exact=False,
                      text=f"{years[0]}-01..{years[-1]} (months of {years[-1]} unknown)")

    def fetch_plan(self, product, start, end):
        last_year = end.year if end is not None else max(self.zip_urls, default=start.year)
        years = [y for y in range(start.year, last_year + 1) if y in self.zip_urls]
        if not years:
            return ["nothing listed upstream for these years"]
        cached = [y for y in years if len(list((self.workdir / "raw" / str(y)).rglob("*.nc"))) == 12]
        return [f"{len(years)} yearly zips {years[0]}-{years[-1]} (~180 MB each) from {DOWNLOAD_ROOT}, "
                f"{len(cached)} already extracted in {self.workdir / 'raw'}"]

    def _year_files(self, year, wanted):
        """{month: file} of a year, downloading the zip unless the wanted months are cached
        (wanted None: always download, the year may have grown upstream)."""
        outdir = self.workdir / "raw" / str(year)
        def present():
            return {pd.Period(re.search(r"(\d{6})\.nc$", f.name)[1], freq="M"): f
                    for f in outdir.rglob("*.nc")}
        files = present()
        if wanted is not None and wanted <= set(files):
            return files
        url = self.zip_urls.get(year)
        if url is None:
            return files
        zpath = self.fetcher.download(url, self.workdir / "raw" / url.rsplit("/", 1)[1],
                                      validator=nonempty, overwrite=True)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(outdir)
        zpath.unlink()
        return present()

    def fetch(self, product, start, end):
        """{month: raw monthly file} for the months of start..end available upstream."""
        last = end if end is not None else pd.Period(f"{max(self.zip_urls, default=start.year)}-12", freq="M")
        files = {}
        for year in range(start.year, last.year + 1):
            wanted = {p for p in pd.period_range(start, last, freq="M") if p.year == year}
            if end is None and year == last.year:
                wanted = None  # unknown number of months: take what the zip has
            files.update({p: f for p, f in self._year_files(year, wanted).items() if start <= p <= last})
        return files

    def _processed(self, month, raw):
        """CMORized month regridded with cdo remapbil, cached in the workdir."""
        out = self.workdir / "processed" / f"EN4_{month.strftime('%Y%m')}.nc"
        if out.exists() and out.stat().st_mtime >= Path(raw).stat().st_mtime:
            return out
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".cmor.nc")
        with xr.open_dataset(raw) as ds:
            cmorize(ds).to_netcdf(tmp)
        cdo.cdo("-f", "nc4", f"remapbil,{TARGET_GRID}", tmp, out)
        tmp.unlink()
        return out

    def build(self, product, raw, start, end, template=None):
        if not raw:
            return xr.Dataset(coords={"time": pd.DatetimeIndex([])})
        paths = [self._processed(month, raw[month]) for month in sorted(raw)]
        ds = xr.open_mfdataset(paths, combine="by_coords", data_vars="minimal", coords="minimal",
                               compat="override")
        variables = [v for names in product.files.values() for v in names]
        ds = ds[variables + [v for v in ds.data_vars if v.endswith("_bnds")]]
        if template is not None and "time" in template:
            ds["time"].encoding = dict(template["time"].encoding)
        return ds

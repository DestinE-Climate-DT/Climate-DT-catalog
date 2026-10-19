"""PSC PIOMAS (Arctic) and GIOMAS (global) monthly sea-ice thickness from the annual binaries."""

import datetime
import gzip
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from ..base import CatalogEntry, ObsDataset, Product, Remote
from ..fetch import DownloadError, gzip_multiple, size_multiple
from ..timeaxis import month_bounds, month_starts

log = logging.getLogger(__name__)

PSC = "https://pscfiles.apl.washington.edu/zhang"
NX = 360

MODELS = {
    "piomas": {
        "ny": 120,
        "heff_url": f"{PSC}/PIOMAS/data/v2.1/heff",
        "grid_url": f"{PSC}/PIOMAS/utilities",
        "mask_file": "io.dat_360_120.output",
        "missing": None,  # no setctomiss in the historical PIOMAS processing
        "model": "Panarctic Ice/Ocean Modeling and Assimilation System (PIOMAS)",
        "doc": "https://psc.apl.uw.edu/research/projects/arctic-sea-ice-volume-anomaly/data/model_grid",
    },
    "giomas": {
        "ny": 276,
        "heff_url": f"{PSC}/Global_seaice",
        "grid_url": f"{PSC}/Global_seaice",
        "mask_file": "io.dat_360_276.output",
        "missing": 9999.9,
        "model": "Global Ice-Ocean Modeling and Assimilation System (GIOMAS)",
        "doc": "https://psc.apl.washington.edu/zhang/Global_seaice/data.html",
    },
}


def read_heff(path, ny):
    """Read one annual heff binary (gzipped or raw) as a (nmonths, ny, 360) float32 array.

    The file of the current year holds only the months published so far."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as fh:
        data = np.frombuffer(fh.read(), dtype="<f4")
    return data.reshape(-1, ny, NX)


def read_ascii_floats(path):
    """All the whitespace-separated numbers of an ASCII grid file."""
    return np.array(Path(path).read_text().split(), dtype=float)


def read_mask(path, ny):
    """Ocean mask from io.dat_360_<ny>.output: odd characters > 0 mean ocean."""
    rows = [line.rstrip("\n") for line in Path(path).read_text().splitlines() if line.strip()]
    mask = [[1 if int(row[j]) > 0 else 0 for j in range(1, NX * 2, 2)] for row in rows[:ny]]
    return np.array(mask, dtype="f4")


class PSC(ObsDataset):
    name = "psc"
    catalog_dir = "PSC"
    description = "PSC PIOMAS/GIOMAS monthly sea-ice thickness"
    start_year = 1979
    complete_years = True

    def all_products(self):
        return [Product(key, f"sithick_r1i1p1_mon_{{start}}-{{end}}_GCCS{NX}x{model['ny']}_curvgrid.nc",
                        f"PSC/{key.upper()}", catalog=[CatalogEntry(f"{key}.yaml", "monthly")],
                        params=dict(model))
                for key, model in MODELS.items()]

    @staticmethod
    def _month_bytes(product):
        return product.params["ny"] * NX * 4

    def _listing(self, product):
        """{year: compressed?} of the heff files upstream."""
        years = {}
        for m in self.fetcher.listing(product.params["heff_url"] + "/", r"heff\.H(\d{4})(\.gz)?"):
            years[int(m[1])] = years.get(int(m[1]), False) or bool(m[2])
        return years

    def remote_info(self, product):
        years = self._listing(product)
        if not years:
            return Remote(text="nothing listed")
        last_year = max(years)
        nmonths = 12
        if not years[last_year]:  # raw binary: possibly the current, incomplete year
            sig = self.fetcher.head(f"{product.params['heff_url']}/heff.H{last_year}")
            nmonths = sig["size"] // self._month_bytes(product)
        last = pd.Period(f"{last_year}-{nmonths:02d}", freq="M")
        return Remote(last=last, text=f"{min(years)}-01..{last}")

    def fetch(self, product, start, end):
        """{year: local file} for the years of start..end available upstream."""
        listed = self._listing(product)
        last_year = end.year if end is not None else max(listed, default=start.year)
        base, unit = product.params["heff_url"], self._month_bytes(product)
        dest = self.workdir / "raw" / product.key
        files = {}
        for year in range(start.year, last_year + 1):
            if year not in listed:
                continue
            if listed[year]:
                try:
                    files[year] = self.fetcher.download(f"{base}/heff.H{year}.gz", dest / f"heff.H{year}.gz",
                                                        validator=gzip_multiple(unit))
                    continue
                except DownloadError as exc:
                    log.debug("%s", exc)
            # raw files are re-downloaded when upstream has grown (current year)
            url, path = f"{base}/heff.H{year}", dest / f"heff.H{year}"
            sig = self.fetcher.head(url)
            if sig is None:
                continue
            stale = path.exists() and sig["size"] is not None and path.stat().st_size != sig["size"]
            files[year] = self.fetcher.download(url, path, validator=size_multiple(unit), overwrite=stale)
        return files

    def _grid_file(self, product, name):
        return self.fetcher.download(f"{product.params['grid_url']}/{name}",
                                     self.workdir / "grids" / product.key / name)

    def build(self, product, raw, start, end, template=None):
        ny = product.params["ny"]
        if not raw:
            return xr.Dataset(coords={"time": pd.DatetimeIndex([])})
        arrays, times = [], []
        for year in sorted(raw):
            data = read_heff(raw[year], ny)
            arrays.append(data)
            times.append(month_starts(pd.Period(f"{year}-01", freq="M"),
                                      pd.Period(f"{year}-{len(data):02d}", freq="M")))
        data, times = np.concatenate(arrays), times[0].append(times[1:])
        if product.params["missing"] is not None:
            data = np.where(np.isclose(data, product.params["missing"]), np.nan, data).astype("f4")
        if template is not None:
            return self._like_template(data, times, template)
        return self._from_scratch(product, data, times, [Path(raw[y]).name for y in sorted(raw)])

    @staticmethod
    def _like_template(data, times, template):
        """New time steps laid out as the existing product (dims, time bounds)."""
        ds = xr.Dataset({"sithick": (template["sithick"].dims, data)}, coords={"time": times})
        bounds = template["time"].attrs.get("bounds")
        if bounds and bounds in template:
            ds[bounds] = (template[bounds].dims, month_bounds(times))
        return ds

    def _from_scratch(self, product, data, times, names):
        """Full product from the PSC grid files, as in the original Massonnet/Tovazzi script."""
        ny, p = product.params["ny"], product.params
        lonlat = read_ascii_floats(self._grid_file(product, "grid.dat"))
        pop = read_ascii_floats(self._grid_file(product, "grid.dat.pop"))
        mask = read_mask(self._grid_file(product, p["mask_file"]), ny)
        n = ny * NX
        htn, hte = pop[2 * n:3 * n].reshape(ny, NX), pop[3 * n:4 * n].reshape(ny, NX)
        ds = xr.Dataset(
            {"sithick": (("time", "y", "x"), data,
                         {"units": "m", "long_name": "Sea ice thickness",
                          "standard_name": "sea_ice_thickness", "coordinates": "lat lon"}),
             "time_bnds": (("time", "bnds"), month_bounds(times)),
             "areacello": (("y", "x"), (htn * 1e3 * hte * 1e3).astype("f4"),
                           {"units": "m2", "long_name": "Ocean grid-cell area",
                            "standard_name": "cell_area"}),
             "sftof": (("y", "x"), mask, {"units": "1", "long_name": "Sea fraction (0=land, 1=ocean)",
                                          "standard_name": "sea_area_fraction"})},
            coords={"time": ("time", times, {"standard_name": "time", "axis": "T", "bounds": "time_bnds"}),
                    "lon": (("y", "x"), lonlat[:n].reshape(ny, NX).astype("f4"),
                            {"units": "degrees_east", "standard_name": "longitude"}),
                    "lat": (("y", "x"), lonlat[n:2 * n].reshape(ny, NX).astype("f4"),
                            {"units": "degrees_north", "standard_name": "latitude"})})
        ds["time"].encoding = {"units": "days since 1979-01-01 00:00:00", "calendar": "gregorian"}
        ds.attrs = {"Model": p["model"], "Conventions": "CF-1.8", "raw_data": ", ".join(names),
                    "file_created": "Created " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "processing_info": f"grid files from {p['doc']}"}
        log.warning("%s: built from scratch; check the grid against the previous curvgrid product",
                    product.key)
        return ds

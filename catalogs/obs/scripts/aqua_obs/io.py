"""Read, extend and write the netCDF output products."""

import datetime
import logging
import os
from pathlib import Path

import numpy as np
import xarray as xr

from .timeaxis import monthly_gaps

log = logging.getLogger(__name__)

# encoding keys carried over from the reference file
KEEP_ENCODING = ("dtype", "zlib", "complevel", "shuffle", "compression", "_FillValue",
                 "units", "calendar", "scale_factor", "add_offset")


class CompatibilityError(ValueError):
    """New data cannot be appended to the existing product."""


def open_product(path):
    """Open an existing product lazily."""
    return xr.open_dataset(path, chunks={})


def time_vars(ds, dim="time"):
    """Data variables depending on dim."""
    return [v for v in ds.data_vars if dim in ds[v].dims]


def check_compatible(reference, new, dim="time", atol=1e-4):
    """Check that new has the time-dependent variables, dims and grid of reference."""
    ref_vars, new_vars = set(time_vars(reference, dim)), set(time_vars(new, dim))
    if not ref_vars <= new_vars:
        raise CompatibilityError(f"new data lack {sorted(ref_vars - new_vars)} of the existing product")
    if new_vars - ref_vars:
        log.warning("Ignoring variables not in the existing product: %s", sorted(new_vars - ref_vars))
    for var in ref_vars:
        if reference[var].dims != new[var].dims:
            raise CompatibilityError(f"{var}: dims {reference[var].dims} vs {new[var].dims}")
        ref_shape = {d: s for d, s in reference[var].sizes.items() if d != dim}
        new_shape = {d: s for d, s in new[var].sizes.items() if d != dim}
        if ref_shape != new_shape:
            raise CompatibilityError(f"{var}: shape {ref_shape} vs {new_shape}")
        ref_units, new_units = reference[var].attrs.get("units"), new[var].attrs.get("units")
        if ref_units and new_units and ref_units != new_units:
            raise CompatibilityError(f"{var}: units {ref_units} vs {new_units}")
    for name, coord in reference.coords.items():
        if dim in coord.dims or name not in new.coords:
            continue
        if coord.shape != new[name].shape or not np.allclose(coord.values, new[name].values, atol=atol,
                                                             equal_nan=True):
            raise CompatibilityError(f"coordinate {name} differs from the existing product")


def _adopt(reference, new, dim="time"):
    """new restricted to the time-dependent variables of reference, with its static coordinates
    and attributes, plus the static variables of reference."""
    check_compatible(reference, new, dim)
    dynamic = time_vars(reference, dim)
    static_coords = {c: reference[c] for c in reference.coords if dim not in reference[c].dims}
    new = new[dynamic].assign_coords(static_coords)
    for var in dynamic:
        new[var].attrs = reference[var].attrs
    static = reference[[v for v in reference.data_vars if v not in dynamic]]
    return new, static


def _finish(combined, reference, dim="time"):
    combined.attrs = dict(reference.attrs)
    for var in combined.variables:
        if var in reference.variables:
            combined[var].encoding = dict(reference[var].encoding)
    problems = monthly_gaps(combined[dim].values)
    if problems:
        raise CompatibilityError("; ".join(problems))
    return combined


def append_time(reference, new, dim="time"):
    """Concatenate new time steps after reference, keeping static variables of reference.

    Non-time coordinates are taken from reference, so the grid description of the existing
    product (curvilinear coordinates, bounds, cell areas...) is preserved verbatim.
    """
    last_ref, first_new = reference[dim].values[-1], new[dim].values[0]
    if not first_new > last_ref:
        raise CompatibilityError(f"new data start ({first_new}) does not follow existing end ({last_ref})")
    new, static = _adopt(reference, new, dim)
    combined = xr.concat([reference[list(new.data_vars)], new], dim=dim, data_vars="minimal",
                         coords="minimal", compat="override", join="override")
    combined = xr.merge([combined, static], compat="override", join="override")
    return _finish(combined, reference, dim)


def like_template(template, new, dim="time"):
    """new laid out as template (grid, static fields, attributes, encoding), without its data."""
    new, static = _adopt(template, new, dim)
    combined = xr.merge([new, static], compat="override", join="override")
    return _finish(combined, template, dim)


def add_history(ds, message):
    """Prepend a timestamped line to the history attribute."""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old = ds.attrs.get("history")
    ds.attrs["history"] = f"{stamp}: {message}" + (f"\n{old}" if old else "")
    return ds


def netcdf_encoding(ds, complevel=1):
    """Encoding preserving dtype/compression/fill of the source variables, zlib by default.

    Datetimes without units get 'days since <first year>-01-01', shared with their bounds."""
    encoding = {}
    for name, var in ds.variables.items():
        enc = {k: v for k, v in var.encoding.items() if k in KEEP_ENCODING}
        if np.issubdtype(var.dtype, np.datetime64) and "units" not in enc:
            owner = next((v for v in ds.variables if ds[v].attrs.get("bounds") == name), name)
            units = ds[owner].encoding.get("units")
            enc["units"] = units or f"days since {str(ds[owner].values.min())[:4]}-01-01"
        if name in ds.data_vars and np.issubdtype(var.dtype, np.number) and var.ndim > 1:
            if "compression" not in enc and "zlib" not in enc:
                enc.update(zlib=True, complevel=complevel)
        if name in ds.coords and "_FillValue" not in enc:
            enc["_FillValue"] = None
        encoding[name] = enc
    return encoding


def write_netcdf(ds, path, complevel=1):
    """Write a netCDF4 file atomically (tmp file + rename, safe for DVC-linked targets)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    log.info("Writing %s", path)
    ds.to_netcdf(tmp, format="NETCDF4", encoding=netcdf_encoding(ds, complevel))
    os.replace(tmp, path)
    return path

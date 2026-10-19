import numpy as np
import pandas as pd
import pytest
import xarray as xr

from aqua_obs import io
from aqua_obs.timeaxis import month_bounds, month_starts


def make(years, static=True):
    times = month_starts(pd.Period(f"{years[0]}-01", freq="M"), pd.Period(f"{years[-1]}-12", freq="M"))
    ds = xr.Dataset({"tas": (("time", "y", "x"), np.random.rand(len(times), 3, 4).astype("f4"),
                             {"units": "K"}),
                     "time_bnds": (("time", "bnds"), month_bounds(times))},
                    coords={"time": ("time", times, {"bounds": "time_bnds"}),
                            "lon": (("y", "x"), np.arange(12.0).reshape(3, 4))})
    if static:
        ds["area"] = (("y", "x"), np.ones((3, 4)))
    return ds


def test_append_keeps_static_and_reference_grid():
    ref, new = make([2020]), make([2021], static=False)
    new = new.assign_coords(lon=new.lon + 1e-6)  # tiny differences: reference grid wins
    out = io.append_time(ref, new)
    assert out.sizes["time"] == 24
    assert "area" in out and "time" not in out["area"].dims
    np.testing.assert_array_equal(out.lon, ref.lon)
    np.testing.assert_array_equal(out.tas.isel(time=slice(12, None)), new.tas)


def test_append_rejects_overlap_gap_and_grid():
    ref = make([2020])
    with pytest.raises(io.CompatibilityError, match="does not follow"):
        io.append_time(ref, make([2020]))
    with pytest.raises(io.CompatibilityError, match="gap"):
        io.append_time(ref, make([2022]))
    with pytest.raises(io.CompatibilityError, match="coordinate lon"):
        io.append_time(ref, make([2021]).assign_coords(lon=lambda d: d.lon + 1))
    with pytest.raises(io.CompatibilityError, match="lack"):
        io.append_time(ref, make([2021]).drop_vars("time_bnds"))


def test_write_netcdf_keeps_encoding(tmp_path):
    ref = make([2020])
    first = io.write_netcdf(ref, tmp_path / "a.nc")
    with xr.open_dataset(first) as opened:
        out = io.append_time(opened, make([2021], static=False))
        io.write_netcdf(out, tmp_path / "b.nc")
    with xr.open_dataset(tmp_path / "b.nc") as res:
        assert res.tas.dtype == np.float32
        assert res.tas.encoding["zlib"]
        assert res.sizes["time"] == 24
        assert "_FillValue" not in res.lon.encoding


def test_extend_zarr(tmp_path):
    store = io.write_zarr(make([2020]), tmp_path / "a.zarr", chunks={"time": 1})
    new = io.extend_zarr(store, make([2021], static=False), tmp_path / "b.zarr", chunks={"time": 1})
    with xr.open_zarr(new) as res, xr.open_zarr(store) as old:
        assert res.sizes["time"] == 24 and old.sizes["time"] == 12
        assert res.tas.chunks[0] == (1,) * 24
    with pytest.raises(FileExistsError):
        io.extend_zarr(store, make([2021]), new)


def test_like_template():
    ref, new = make([2020]), make([1990, 1991], static=False)
    out = io.like_template(ref, new)
    assert out.sizes["time"] == 24 and "area" in out
    np.testing.assert_array_equal(out.lon, ref.lon)

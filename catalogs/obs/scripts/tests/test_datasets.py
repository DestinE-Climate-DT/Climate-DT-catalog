"""End-to-end updates of PSC against a local HTTP server, plus dataset helpers."""

import gzip

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from aqua_obs import io
from aqua_obs.base import ObsDataset
from aqua_obs.datasets import berkeley, en4, psc
from aqua_obs.timeaxis import month_bounds, month_starts, select_months

NY = 4
M = lambda s: pd.Period(s, freq="M")  # noqa: E731


@pytest.fixture
def piomas(monkeypatch, http_dir, settings):
    """Upstream with 2001 (gz), 2002 (raw) and 2003 (raw, 5 months); catalog aligned with
    a local product 199901-200012."""
    root, url = http_dir
    monkeypatch.setitem(psc.MODELS, "piomas", {**psc.MODELS["piomas"], "ny": NY, "heff_url": url})
    with gzip.open(root / "heff.H2001.gz", "wb") as fh:
        fh.write(heff(2001))
    (root / "heff.H2002").write_bytes(heff(2002))
    (root / "heff.H2003").write_bytes(heff(2003, months=5))
    yaml = settings.catalog_root / "catalog" / "PSC" / "piomas.yaml"
    yaml.write_text(yaml.read_text().replace("197901-202512_GCCS360x120", "199901-200012_GCCS360x4"))
    return root


def heff(year, months=12):
    """Synthetic binary: value = year + month index (constant over the grid)."""
    return np.repeat(np.arange(months, dtype="<f4") + year, NY * psc.NX).tobytes()


def existing_product(settings, first, last):
    """A previous product, curvilinear grid as written by cdo setgrid."""
    times = month_starts(M(first), M(last))
    ds = xr.Dataset(
        {"sithick": (("time", "y", "x"), np.zeros((len(times), NY, psc.NX), "f4"),
                     {"units": "m", "coordinates": "lat lon"}),
         "time_bnds": (("time", "bnds"), month_bounds(times)),
         "areacello": (("y", "x"), np.ones((NY, psc.NX), "f4"))},
        coords={"time": ("time", times, {"bounds": "time_bnds"}),
                "lon": (("y", "x"), np.ones((NY, psc.NX))), "lat": (("y", "x"), np.ones((NY, psc.NX)))})
    name = f"sithick_r1i1p1_mon_{first.replace('-', '')}-{last.replace('-', '')}_GCCS360x{NY}_curvgrid.nc"
    return io.write_netcdf(ds, settings.output_root / "PSC" / "PIOMAS" / name)



def test_registry():
    assert {"BERKELEY-EARTH", "EN4", "PSC"} <= set(ObsDataset.registry)


def test_psc_append_default_complete_years(settings, piomas):
    old = existing_product(settings, "1999-01", "2000-12")
    ds = psc.PSC(settings)
    [status] = ds.check(["PIOMAS"])
    assert status.action == "new data" and status.message == "up to 2002-12"
    assert status.remote == "2001-01..2003-05"

    [result] = ds.update(["PIOMAS"], update_catalog=True)
    assert not result.error and result.mode == "append"
    assert result.outputs[0].name == f"sithick_r1i1p1_mon_199901-200212_GCCS360x{NY}_curvgrid.nc"
    assert result.obsolete == [old]
    with xr.open_dataset(result.outputs[0]) as out:
        assert out.sizes["time"] == 48
        assert "areacello" in out and "time" not in out.areacello.dims
        np.testing.assert_array_equal(out.sithick.isel(y=0, x=0).values[24:27], [2001, 2002, 2003])
        assert out.time_bnds.shape == (48, 2)
    yaml = (settings.catalog_root / "catalog" / "PSC" / "piomas.yaml").read_text()
    assert "199901-200212_GCCS360x4" in yaml

    # only the incomplete 2003 is left: nothing to do by default
    [status] = ds.check(["PIOMAS"])
    assert status.action == "up-to-date"
    [result] = ds.update(["PIOMAS"])
    assert result.outputs == [] and result.message == "nothing new upstream"


def test_psc_append_until_end_month(settings, piomas):
    existing_product(settings, "1999-01", "2002-12")
    ds = psc.PSC(settings)
    [result] = ds.update(["PIOMAS"], end=M("2003-03"))
    assert result.outputs[0].name.startswith("sithick_r1i1p1_mon_199901-200303_")
    assert result.edits == []  # catalog untouched by default
    # beyond what upstream has: error, nothing written
    [result] = ds.update(["PIOMAS"], end=M("2003-08"))
    assert "available only up to 2003-05" in result.error
    assert result.outputs == []
    # append start must follow the local end
    [result] = ds.update(["PIOMAS"], start=M("2003-01"))
    assert "append continues from 2003-04" in result.error


def test_psc_replace_with_template(settings, piomas):
    old = existing_product(settings, "1999-01", "2000-12")
    ds = psc.PSC(settings)
    [result] = ds.update(["PIOMAS"], mode="replace", start=M("2001-01"), end=M("2002-06"))
    assert not result.error and result.mode == "replace"
    assert result.outputs[0].name.startswith("sithick_r1i1p1_mon_200101-200206_")
    with xr.open_dataset(result.outputs[0]) as out:
        assert out.sizes["time"] == 18 and "areacello" in out
    assert old.exists()
    [result] = ds.update(["PIOMAS"], mode="replace", start=M("1990-01"), end=M("2001-12"))
    assert "upstream data start at 2001-01" in result.error


def test_psc_dry_run_touches_nothing(settings, piomas):
    old = existing_product(settings, "1999-01", "2000-12")
    [result] = psc.PSC(settings).update(["PIOMAS"], dry_run=True)
    assert result.mode == "append" and result.message == "(dry run)"
    details = "\n".join(result.details)
    assert "months   : 2001-01..latest available (expected 2002-12), complete years only" in details
    assert f"sithick_r1i1p1_mon_199901-200212_GCCS360x{NY}_curvgrid.nc" in details
    assert "3 yearly heff files 2001-2003" in details
    assert list(old.parent.iterdir()) == [old]


def test_append_needs_local(settings, piomas):
    [result] = psc.PSC(settings).update(["PIOMAS"], mode="append")
    assert "use --mode replace" in result.error


def test_berkeley_full_field():
    time = 1850 + (np.arange(24) + 0.5) / 12
    ds = xr.Dataset({"temperature": (("time", "lat"), np.zeros((24, 2))),
                     "climatology": (("month_number", "lat"), np.arange(24.0).reshape(12, 2))},
                    coords={"time": time})
    out = berkeley.full_field(ds)
    assert out.name == "2t"
    assert str(out.time.values[13])[:10] == "1851-02-01"
    np.testing.assert_array_equal(out.isel(time=13).values, [2.0, 3.0])


def test_en4_cmorize():
    dims = ("time", "depth", "lat", "lon")
    data = np.zeros((1, 2, 2, 2), "f4")
    attrs = {"valid_min": 0, "valid_max": 50, "units": "psu"}
    ds = xr.Dataset({v: (dims, data, dict(attrs)) for v in
                     ("salinity", "salinity_uncertainty", "temperature", "temperature_uncertainty")},
                    coords={"depth": [5.0, 15.0]})
    ds["depth_bnds"] = (("depth", "bnds"), np.zeros((2, 2)))
    out = en4.cmorize(ds)
    assert set(out.data_vars) == {"so", "so_uncertainty", "thetao", "thetao_uncertainty", "depth_bnds"}
    assert "valid_min" not in out.so.attrs and out.so.attrs["standard_name"] == "sea_water_salinity"
    assert out.lev.attrs["positive"] == "down" and out.depth_bnds.dims == ("lev", "bnds")


def test_products_follow_catalog(settings):
    piomas = psc.PSC(settings).all_products()[0]
    assert piomas.key == "PIOMAS:monthly" and piomas.dvc == "PSC/PIOMAS"
    assert piomas.match("sithick_r1i1p1_mon_197901-202512_GCCS360x120_curvgrid.nc") == ("197901", "202512")
    [v422] = en4.EN4(settings).all_products()
    assert v422.key == "v4.2.2:monthly-netcdf" and v422.dvc == "EN4/v4.2.2"
    assert v422.file_keys == ["so", "thetao"]
    assert v422.match("so-EN4-1950-2025.nc", "so") == ("1950", "2025")
    assert v422.match("so-EN4-1950-2025.nc", "thetao") is None
    assert v422.filename(M("1950-01"), M("2026-06"), "thetao") == "thetao-EN4-195001-202606.nc"
    berkeley_keys = [p.key for p in berkeley.BerkeleyEarth(settings).products(["aqua-filled"])]
    assert berkeley_keys == ["aqua-filled:r100-monthly-v1", "aqua-filled:r100-monthly", "aqua-filled:r025-monthly"]


def test_multi_file_product(settings):
    """EN4 v4.2.2: both files are found together, must cover the same months, are split by variable."""
    ds = en4.EN4(settings)
    [product] = ds.all_products()
    folder = settings.output_root / "EN4" / "v4.2.2" / "netcdf"
    times = month_starts(M("2000-01"), M("2000-12"))
    full = xr.Dataset({v: (("time", "lat"), np.zeros((12, 2), "f4"))
                       for v in ("so", "so_uncertainty", "thetao", "thetao_uncertainty")},
                      coords={"time": times, "lat": [0.0, 1.0]})
    full["time_bnds"] = (("time", "bnds"), month_bounds(times))
    so = ds.split(product, full, "so")
    assert set(so.data_vars) == {"so", "so_uncertainty", "time_bnds"}
    io.write_netcdf(so, folder / "so-EN4-2000-2000.nc")
    with pytest.raises(Exception, match="no file for thetao"):
        ds.local_range(product, ds.find_local(product))
    io.write_netcdf(select_months(ds.split(product, full, "thetao"), None, M("2000-06")),
                    folder / "thetao-EN4-200001-200006.nc")
    with pytest.raises(Exception, match="different months"):
        ds.local_range(product, ds.find_local(product))

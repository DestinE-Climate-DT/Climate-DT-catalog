import pandas as pd
import pytest
import xarray as xr

from aqua_obs.timeaxis import month_bounds, month_starts, monthly_gaps, parse_month, select_months

M = lambda s: pd.Period(s, freq="M")  # noqa: E731


def test_month_starts_and_bounds():
    times = month_starts(M("2020-01"), M("2021-12"))
    assert len(times) == 24 and times[0] == pd.Timestamp("2020-01-01")
    bounds = month_bounds(times)
    assert pd.Timestamp(bounds[1, 0]) == pd.Timestamp("2020-02-01")
    assert pd.Timestamp(bounds[-1, 1]) == pd.Timestamp("2022-01-01")


def test_monthly_gaps():
    ok = pd.date_range("2020-01-01", periods=14, freq="MS") + pd.Timedelta(days=15)
    assert monthly_gaps(ok.values) == []
    assert "gap between 2020-05 and 2020-07" in monthly_gaps(ok.delete(5).values)
    assert any("duplicated" in p for p in monthly_gaps(ok.append(ok[-1:]).values))


def test_parse_and_select():
    assert parse_month("202603") == M("2026-03")
    for bad in ("2026", "202613", "2026-03"):
        with pytest.raises(ValueError):
            parse_month(bad)
    ds = xr.Dataset(coords={"time": pd.date_range("2020-01-01", periods=24, freq="MS")})
    sub = select_months(ds, M("2020-03"), M("2020-05"))
    assert [str(t)[:7] for t in sub.time.values] == ["2020-03", "2020-04", "2020-05"]
    assert select_months(ds, M("2021-06"), None).sizes["time"] == 7

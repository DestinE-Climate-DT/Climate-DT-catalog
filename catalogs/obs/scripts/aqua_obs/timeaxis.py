"""Time-axis helpers for monthly observational datasets."""

import re

import numpy as np
import pandas as pd


def to_timestamps(values):
    """Convert numpy datetime64 or cftime values to a pandas DatetimeIndex."""
    values = np.asarray(values)
    if np.issubdtype(values.dtype, np.datetime64):
        return pd.DatetimeIndex(values)
    return pd.DatetimeIndex([pd.Timestamp(v.isoformat()) for v in values])


def months(values):
    """Monthly periods of a time axis."""
    return to_timestamps(values).to_period("M")


def month_range(ds, dim="time"):
    """First and last month of a dataset as pandas Periods."""
    periods = months(ds[dim].values)
    return periods[0], periods[-1]


def parse_month(text):
    """'YYYYMM' -> pandas monthly Period."""
    if text is None:
        return None
    if not re.fullmatch(r"\d{6}", str(text)) or not 1 <= int(str(text)[4:]) <= 12:
        raise ValueError(f"invalid month '{text}', expected YYYYMM")
    return pd.Period(f"{str(text)[:4]}-{str(text)[4:]}", freq="M")


def month_token(period):
    """pandas Period -> 'YYYYMM'."""
    return period.strftime("%Y%m")


def month_starts(first, last):
    """First day of every month between two Periods (inclusive)."""
    return pd.period_range(first, last, freq="M").to_timestamp()


def month_bounds(times):
    """(ntime, 2) array of [month start, next month start] for monthly time steps."""
    starts = months(times)
    return np.stack([starts.to_timestamp().values, (starts + 1).to_timestamp().values], axis=1)


def select_months(ds, first=None, last=None, dim="time"):
    """Subset of ds between two monthly Periods (inclusive, None = open)."""
    periods = months(ds[dim].values)
    keep = np.ones(len(periods), bool)
    if first is not None:
        keep &= periods >= first
    if last is not None:
        keep &= periods <= last
    return ds.isel({dim: np.nonzero(keep)[0]})


def monthly_gaps(times):
    """Return a list of problems (duplicates, unsorted, gaps) of a monthly time axis."""
    periods = months(times)
    problems = []
    if periods.has_duplicates:
        problems.append(f"duplicated months: {sorted(set(periods[periods.duplicated()].astype(str)))}")
    steps = np.diff(periods.asi8)
    if (steps <= 0).any():
        problems.append("time axis not strictly increasing")
    for i in np.nonzero(steps > 1)[0]:
        problems.append(f"gap between {periods[i]} and {periods[i + 1]}")
    return problems

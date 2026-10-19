"""Minimal subprocess wrapper around the CDO command line."""

import logging
import shutil
import subprocess

log = logging.getLogger(__name__)


def cdo(*args, cdo_bin="cdo"):
    """Run `cdo -s <args>` and return stdout. Raises RuntimeError on failure."""
    if shutil.which(cdo_bin) is None:
        raise RuntimeError(f"CDO executable '{cdo_bin}' not found in PATH")
    cmd = [cdo_bin, "-s", *map(str, args)]
    log.debug("Running %s", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{res.stderr}")
    return res.stdout


def fillmiss(infile, outfile):
    """Fill missing values by nearest-neighbour extrapolation, netcdf4 zip output."""
    cdo("-f", "nc4", "-z", "zip", "fillmiss", infile, outfile)

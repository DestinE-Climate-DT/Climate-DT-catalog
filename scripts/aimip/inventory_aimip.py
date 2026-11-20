"""Inventory of the AIMIP archive, input of generate_aimip_catalog.py.

Walks the DRS tree of the AI model submissions and writes a JSON file with:
- "inv": for each "<base>|<experiment>|<table>|<grid_label>|<variable>" the files
  found for each member and version directory;
- "hdr": for each "<base>|<table>|<grid_label>|<variable>" the dimensions of one
  sample file of the ``aimip`` experiment;
- "broken": the files which cannot be opened (e.g. truncated uploads).

Usage (on the machine hosting the data, any python with xarray):
    python inventory_aimip.py /path/to/ai-mip aimip_inventory.json
"""

import json
import os
import sys

import netCDF4
import xarray as xr

# Top-level folders holding model output in DRS layout
MODEL_FOLDERS = ["Ai2", "ArchesWeather", "DLESyM", "Google", "MPI-M", "NVIDIA", "UMD-PARETO"]


def scan(root):
    """Return {key: {member: {version: [files]}}} for all netCDF files below root."""
    inv = {}
    for top in MODEL_FOLDERS:
        for dirpath, _, filenames in os.walk(os.path.join(root, top)):
            files = sorted(f for f in filenames if f.endswith(".nc"))
            if not files:
                continue
            parts = os.path.relpath(dirpath, root).split(os.sep)
            version = parts.pop() if parts[-1].startswith("v20") else "-"
            grid, var, table, member, exp = parts[-1], parts[-2], parts[-3], parts[-4], parts[-5]
            key = "|".join(["/".join(parts[:-5]), exp, table, grid, var])
            inv.setdefault(key, {}).setdefault(member, {})[version] = files
    return inv


def broken_files(root, inv):
    """Return the files, relative to root, which netCDF4 cannot open."""
    broken = []
    for key, members in inv.items():
        base, exp, table, grid, var = key.split("|")
        for member, versions in members.items():
            for version, files in versions.items():
                folder = [base, exp, member, table, var, grid] + ([version] if version != "-" else [])
                for filename in files:
                    try:
                        netCDF4.Dataset(os.path.join(root, *folder, filename)).close()
                    except OSError:
                        broken.append("/".join([*folder, filename]))
    return sorted(broken)


def headers(root, inv, broken):
    """Return the dimensions of each variable, read from one file of the aimip experiment."""
    hdr = {}
    for key, members in inv.items():
        base, exp, table, grid, var = key.split("|")
        hkey = "|".join([base, table, grid, var])
        if hkey in hdr or exp != "aimip":
            continue
        member = sorted(members)[0]
        version = sorted(members[member])[-1]
        folder = [root, base, exp, member, table, var, grid] + ([version] if version != "-" else [])
        readable = [f for f in members[member][version] if "/".join([*folder[1:], f]) not in broken]
        filename = next(f for f in readable if f"_{grid}_" in f)
        with xr.open_dataset(os.path.join(*folder, filename), decode_times=False) as ds:
            hdr[hkey] = {"dims": list(ds[var].dims), "sizes": dict(ds.sizes)}
    return hdr


if __name__ == "__main__":
    inventory = scan(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as out:
        unreadable = broken_files(sys.argv[1], inventory)
        json.dump({"inv": inventory, "hdr": headers(sys.argv[1], inventory, unreadable), "broken": unreadable}, out)

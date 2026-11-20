"""Generate the AQUA catalog of the AIMIP archive (catalogs/aimip/catalog).

The model entries are built from the inventory written by inventory_aimip.py, so
that each source points only to the current version of each file. The reference
datasets (ERA5, GPCP-SG) are few flat files and are described here by hand.

Usage:
    python generate_aimip_catalog.py aimip_inventory.json /path/to/catalogs/aimip
"""

import json
import os
import re
import sys

import yaml

PATH = "{{AIMIP_PATH}}"

# AQUA model name: location in the archive, description and horizontal grid
MODELS = {
    "ACE2-1-ERA5": {"base": "Ai2/ACE2-1-ERA5", "grid": "lon-lat", "description": "ACE2.1-ERA5 AI climate emulator (Ai2)"},
    "ArchesWeather-V2": {
        "base": "ArchesWeather/ArchesWeather-V2",
        "grid": "lon-lat",
        "description": "ArchesWeather-V2 AI model (ArchesWeather)",
    },
    "ArchesWeatherGen-V2": {
        "base": "ArchesWeather/ArchesWeatherGen-V2",
        "grid": "lon-lat",
        "description": "ArchesWeatherGen-V2 generative AI model (ArchesWeather)",
    },
    # DLESyM is on a HEALPix nside=64 face/height/width layout, with no AQUA grid available: no regridding
    "DLESyM": {"base": "DLESyM/DLESyM", "grid": False, "description": "DLESyM AI Earth system model (University of Washington)"},
    "NeuralGCM": {"base": "Google/NeuralGCM", "grid": "lon-lat", "description": "NeuralGCM hybrid AI model, TL63 (Google)"},
    "NeuralGCM-HRD": {
        "base": "Google/NeuralGCM-HRD",
        "grid": "lon-lat",
        "description": "NeuralGCM-HRD hybrid AI model, decoded at 1 degree (Google)",
    },
    "cBottle-1-3": {
        "base": "NVIDIA/CMIP6/AIMIP/NVIDIA/cBottle-1-3",
        "grid": "hpz6-ring",
        "drop_variables": ["crs"],
        "description": "cBottle 1.3 generative AI model, HEALPix nside=64 (NVIDIA)",
    },
    "MD-1p5": {"base": "UMD-PARETO/MD-1p5", "grid": "lon-lat", "description": "MD-1p5 AI model (UMD-PARETO)"},
    "MPI-ESM1-2-LR": {
        "base": "MPI-M/MPI-ESM1-2-LR",
        "grid": "lon-lat",
        "description": "MPI-ESM1.2-LR physical model, CMIP6 reference (MPI-M)",
    },
}

# AQUA experiment name for the experiment folders whose name differs from it
EXPERIMENTS = {"aimip-2k": "aimip-p2k", "aimip-4k": "aimip-p4k", "MPI-ESM1-2-LR/aimip": "amip"}
EXP_DESCRIPTIONS = {
    "aimip": "AIMIP simulation forced by observed SST and sea ice",
    "aimip-p2k": "AIMIP simulation with SST uniformly increased by 2 K",
    "aimip-p4k": "AIMIP simulation with SST uniformly increased by 4 K",
    "amip": "CMIP6 AMIP simulation",
}

FREQUENCIES = {"Amon": "monthly", "day": "daily"}
CHUNKS = {"Amon": 12, "day": 30}
VERTICAL_DIMS = ("plev", "model_layer")
# Variables come in one file each: merge them without comparing or concatenating the coordinates
XARRAY_KWARGS = {"decode_times": True, "combine": "by_coords", "compat": "override", "coords": "minimal", "data_vars": "minimal"}


def date_range(filename):
    """Return the (start, end) dates of a DRS filename, padded to YYYYMMDD."""
    start, end = re.search(r"_(\d+)-(\d+)\.nc$", filename).groups()
    return start.ljust(8, "0"), end.ljust(8, "9")


def select(versions, broken):
    """Split the files of one variable and member into current and discarded ones.

    Unreadable files are discarded. Then the newest version wins: a file of an older
    version is kept only if it does not overlap in time with any file of a newer version.

    Args:
        versions (dict): files for each version directory.
        broken (set): unreadable (version, file) pairs.

    Returns:
        tuple: sets of current and of discarded (version, file) pairs.
    """
    current, superseded = set(), set(broken)
    for version in sorted(versions, reverse=True):
        for filename in versions[version]:
            if (version, filename) in broken:
                continue
            start, end = date_range(filename)
            newer = [date_range(f) for v, f in current if v != version]
            if any(start <= e and end >= s for s, e in newer):
                superseded.add((version, filename))
            else:
                current.add((version, filename))
    return current, superseded


def patterns(base, exp, table, grid, var, members, broken):
    """Return the glob patterns matching the current files of one variable for any member.

    One pattern for each version directory is enough when all its files are current.
    When some members have discarded files there, the pattern is split by time
    period and those members are excluded through their realization index.
    """
    folder = f"{PATH}/{base}/{exp}/{{{{realization}}}}/{table}/{var}/{grid}"
    selection = {}
    for member, versions in members.items():
        relative = f"{base}/{exp}/{member}/{table}/{var}/{grid}/"
        unreadable = {tuple(b[len(relative) :].split("/")) for b in broken if b.startswith(relative)}
        selection[member] = select(versions, unreadable)
    out = []
    for version in sorted({v for current, _ in selection.values() for v, _ in current}):
        prefix = f"{folder}/{version}/" if version != "-" else f"{folder}/"
        periods = {}  # time period of the filename: members for which that file is superseded
        for member, (current, superseded) in selection.items():
            for flag, pairs in ((False, current), (True, superseded)):
                for _, filename in (p for p in pairs if p[0] == version and f"_{grid}_" in p[1]):
                    periods.setdefault(filename.rsplit("_", 1)[1], set()).update([member] if flag else [])
        if not any(periods.values()):
            out.append(f"{prefix}{var}_*_{grid}_*.nc")
            continue
        for period, excluded in sorted(periods.items()):
            if not excluded:
                out.append(f"{prefix}{var}_*_{grid}_{period}")
                continue
            indices = [re.fullmatch(r"r(\d)i1p1f1", member) for member in sorted(excluded)]
            if not all(indices):
                raise ValueError(f"Cannot exclude members {excluded} of {base} {exp} {var} with a glob")
            out.append(f"{prefix}{var}_*_r[!{''.join(i.group(1) for i in indices)}]i1p1f1_{grid}_{period}")
    return out


def model_sources(inv, hdr, broken, exp, config):
    """Return the AQUA sources of one experiment and the sorted list of its members."""
    base = config["base"]
    xarray_kwargs = {**XARRAY_KWARGS, **{k: config[k] for k in ("drop_variables",) if k in config}}
    groups = {}  # (table, grid label, 2d/3d): variables
    for key in inv:
        kbase, kexp, table, grid, var = key.split("|")
        if (kbase, kexp) == (base, exp):
            dims = hdr["|".join([base, table, grid, var])]["dims"]
            kind = "atm3d" if set(dims) & set(VERTICAL_DIMS) else "atm2d"
            groups.setdefault((table, grid, kind), []).append(var)

    sources, all_members = {}, set()
    for (table, grid, kind), variables in sorted(groups.items()):
        # The regridded (gr) data are the default source when both grid labels are available
        native = grid == "gn" and (table, "gr", kind) in groups
        name = f"{FREQUENCIES[table]}-{kind}" + ("-native" if native else "")
        members = sorted({m for var in variables for m in inv["|".join([base, exp, table, grid, var])]})
        all_members.update(members)
        urlpath = [
            p
            for var in sorted(variables)
            for p in patterns(base, exp, table, grid, var, inv["|".join([base, exp, table, grid, var])], broken)
        ]
        sources[name] = {
            "description": f"{FREQUENCIES[table]} {kind[3:].upper()} data on the {grid} grid ({', '.join(sorted(variables))})",
            "driver": "netcdf",
            "metadata": {"source_grid_name": config["grid"]},
            "args": {"urlpath": urlpath, "chunks": {"time": CHUNKS[table]}, "xarray_kwargs": dict(xarray_kwargs)},
            "parameters": {
                "realization": {"description": "ensemble member", "type": "str", "default": members[0], "allowed": members}
            },
        }
    return sources, sorted(all_members)


def reference_source(description, urlpath, time_chunk, grid="lon-lat"):
    """Return the AQUA source of a reference dataset."""
    return {
        "description": description,
        "driver": "netcdf",
        "metadata": {"source_grid_name": grid},
        "args": {"urlpath": urlpath, "chunks": {"time": time_chunk}, "xarray_kwargs": dict(XARRAY_KWARGS)},
    }


# Reference datasets: model -> (description, {exp: (description, sources)})
ERA5_1DEG = f"{PATH}/ERA5/mon_1deg/native6_ERA5_*_v1"
ERA5_025 = f"{PATH}/ERA5/mon/ERA5"
ERA5_2D = ["ps", "psl", "tas", "ts", "uas", "vas", "pr"]
REFERENCES = {
    "ERA5": (
        "ERA5 reanalysis, reference for AIMIP",
        {
            "era5": (
                "ERA5 monthly means: 1 degree AIMIP evaluation set (1978-2024) and 0.25 degree fields (1940-2024)",
                {
                    "monthly-atm2d": reference_source(
                        "monthly 2D data at 1 degree, CMOR names (1978-2024)",
                        [f"{ERA5_1DEG}_Amon_{v}_1978-2024.nc" for v in sorted(ERA5_2D)] + [f"{ERA5_1DEG}_Emon_tdps_1978-2024.nc"],
                        12,
                    ),
                    "monthly-atm3d": reference_source(
                        "monthly 3D data at 1 degree on 8 pressure levels, CMOR names (1978-2024)",
                        [f"{ERA5_1DEG}_Amon_{v}_1978-2024.nc" for v in ["hus", "ta", "ua", "va"]],
                        12,
                    ),
                    "monthly-atm3d-zg": reference_source(
                        "monthly geopotential height at 1 degree on 37 pressure levels (1978-2024)",
                        f"{ERA5_1DEG}_Amon_zg_1978-2024.nc",
                        12,
                    ),
                    "monthly-r025-atm2d": reference_source(
                        "monthly 2D data at 0.25 degree, ERA5 names (1940-2024)", f"{ERA5_025}_*_mon_full_sfc_1940-2024.nc", 1
                    ),
                    "monthly-r025-atm3d": reference_source(
                        "monthly 3D data at 0.25 degree on 8 pressure levels, ERA5 names (1940-2024)",
                        f"{ERA5_025}_*_mon_full_plev8_1940-2024.nc",
                        1,
                    ),
                },
            )
        },
    ),
    "GPCP-SG": (
        "GPCP-SG precipitation, reference for AIMIP",
        {
            "v2.3": (
                "GPCP-SG v2.3 monthly precipitation interpolated to 1 degree",
                {
                    "monthly": reference_source(
                        "monthly precipitation at 1 degree (1979-2024)",
                        f"{PATH}/GPCP-SG/OBS_GPCP-SG_atmos_2.3_Amon_pr_1979-2024.nc",
                        12,
                    )
                },
            )
        },
    ),
}


def dump(content, *path):
    """Write a catalog YAML file, creating its folder."""
    os.makedirs(os.path.join(*path[:-1]), exist_ok=True)
    with open(os.path.join(*path), "w", encoding="utf-8") as out:
        yaml.safe_dump(content, out, sort_keys=False, width=200)


def nested(description, target):
    """Return a catalog entry pointing to another YAML file."""
    return {"description": description, "driver": "yaml_file_cat", "args": {"path": target}}


def main(inventory, outdir):
    with open(inventory, encoding="utf-8") as stream:
        content = json.load(stream)
    inv, hdr, broken = content["inv"], content["hdr"], content["broken"]

    top = {}
    for model, config in MODELS.items():
        exps = {}
        for folder in sorted({k.split("|")[1] for k in inv if k.split("|")[0] == config["base"]}):
            exp = EXPERIMENTS.get(f"{model}/{folder}", EXPERIMENTS.get(folder, folder))
            sources, members = model_sources(inv, hdr, broken, folder, config)
            dump({"sources": sources}, outdir, "catalog", model, f"{exp}.yaml")
            description = f"{EXP_DESCRIPTIONS[exp]}, {len(members)} member{'s' if len(members) > 1 else ''}"
            exps[exp] = nested(description, f"{{{{CATALOG_DIR}}}}/{exp}.yaml")
        dump({"sources": exps}, outdir, "catalog", model, "main.yaml")
        top[model] = nested(config["description"], f"{{{{CATALOG_DIR}}}}/catalog/{model}/main.yaml")

    for model, (description, experiments) in REFERENCES.items():
        exps = {}
        for exp, (exp_description, sources) in experiments.items():
            dump({"sources": sources}, outdir, "catalog", model, f"{exp}.yaml")
            exps[exp] = nested(exp_description, f"{{{{CATALOG_DIR}}}}/{exp}.yaml")
        dump({"sources": exps}, outdir, "catalog", model, "main.yaml")
        top[model] = nested(description, f"{{{{CATALOG_DIR}}}}/catalog/{model}/main.yaml")

    parameters = {
        "AIMIP_PATH": {
            "type": "str",
            "description": "the path to the AIMIP archive on the local machine",
            "default": "/work/ab0995/a270088/AIMIP/minio_copy/ai-mip",
        }
    }
    dump({"metadata": {"parameters": parameters}, "sources": top}, outdir, "catalog.yaml")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

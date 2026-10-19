"""Configuration: suite config.yaml layered over the catalog machine.yaml and CLI options."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = SCRIPTS_DIR / "config.yaml"


class ConfigError(RuntimeError):
    """Invalid or incomplete configuration."""


@dataclass
class Settings:
    """Resolved settings for one run."""
    machine: str
    output_root: Path
    workdir: Path
    catalog_root: Path          # catalogs/obs
    data_path: Path | None = None
    retries: int = 5
    timeout: int = 60
    update_catalog: bool = False  # edit the catalog yaml after an update
    datasets: dict = field(default_factory=dict)

    def dataset_options(self, name):
        """Options of a dataset (catalog model name, case-insensitive)."""
        for key, opts in self.datasets.items():
            if key.lower() == name.lower():
                return dict(opts or {})
        return {}


def aqua_machine():
    """Machine name from the AQUA configuration ($AQUA_CONFIG or ~/.aqua), if any."""
    configdir = Path(os.environ.get("AQUA_CONFIG", Path.home() / ".aqua"))
    cfg = configdir / "config-aqua.yaml"
    if not cfg.exists():
        return None
    with open(cfg) as fh:
        return (yaml.safe_load(fh) or {}).get("machine")


def _path(value):
    return Path(os.path.expandvars(os.path.expanduser(str(value)))) if value else None


def load_settings(config=None, machine=None, output_root=None, workdir=None):
    """Resolve settings. Priority: CLI arguments > config.yaml machines > machine.yaml intake."""
    config = Path(config) if config else DEFAULT_CONFIG
    with open(config) as fh:
        cfg = yaml.safe_load(fh) or {}
    catalog_root = _path(cfg.get("catalog_root")) or config.resolve().parents[1]
    if not catalog_root.is_absolute():
        catalog_root = (config.resolve().parent / catalog_root).resolve()

    machine = machine or cfg.get("machine", "auto")
    if machine == "auto":
        machine = aqua_machine()
        if not machine:
            raise ConfigError("machine is 'auto' but no AQUA config found: use --machine")
        log.info("Machine from AQUA config: %s", machine)

    machine_file = catalog_root / "machine.yaml"
    machines = yaml.safe_load(machine_file.read_text()) if machine_file.exists() else {}
    intake = (machines.get(machine) or {}).get("intake") or {}
    override = (cfg.get("machines") or {}).get(machine) or {}
    if machine not in machines and not override:
        raise ConfigError(f"machine '{machine}' is neither in {machine_file} nor in {config}")

    output_root = _path(output_root) or _path(override.get("output_root")) or _path(intake.get("DVC_PATH"))
    if output_root is None:
        raise ConfigError(f"no output_root for '{machine}': no DVC_PATH in machine.yaml, "
                          f"set output_root in {config} or use --output-root")
    defaults = cfg.get("defaults") or {}
    workdir = _path(workdir) or _path(override.get("workdir")) or _path(defaults.get("workdir"))
    if workdir is None:
        raise ConfigError(f"no workdir for '{machine}': set machines.{machine}.workdir "
                          f"in {config} or use --workdir")

    # a machine may edit another copy of the catalog (e.g. a scratch copy for local tests)
    if override.get("catalog_root"):
        catalog_root = _path(override["catalog_root"])

    # dataset options: machine-specific values override the global ones, key by key
    # (dataset names are case-insensitive)
    datasets = {name.lower(): dict(opts or {}) for name, opts in (cfg.get("datasets") or {}).items()}
    for name, opts in (override.get("datasets") or {}).items():
        datasets.setdefault(name.lower(), {}).update(opts or {})

    return Settings(machine=machine, output_root=output_root, workdir=workdir,
                    catalog_root=catalog_root, data_path=_path(intake.get("DATA_PATH")),
                    retries=defaults.get("retries", 5), timeout=defaults.get("timeout", 60),
                    update_catalog=bool(override.get("update_catalog", cfg.get("update_catalog", False))),
                    datasets=datasets)

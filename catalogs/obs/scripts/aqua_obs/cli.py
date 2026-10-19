"""aqua-obs command line interface."""

import argparse
import logging
import sys

from . import __version__
from .base import MODES, ObsDataset
from .config import ConfigError, load_settings
from .timeaxis import parse_month
from . import datasets  # noqa: F401  (registers the datasets)

log = logging.getLogger("aqua_obs")


def parse_targets(targets):
    """'psc' or 'psc:piomas' -> {dataset: [products] or None}."""
    selection = {}
    for target in targets:
        name, _, product = target.partition(":")
        if name not in ObsDataset.registry:
            raise SystemExit(f"unknown dataset '{name}', available: {', '.join(sorted(ObsDataset.registry))}")
        if not product:
            selection[name] = None  # whole dataset
        elif name not in selection:
            selection[name] = [product]
        elif selection[name] is not None:
            selection[name].append(product)
    return selection


def month_arg(text):
    try:
        return parse_month(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser():
    parser = argparse.ArgumentParser(prog="aqua-obs", description=(
        "Check upstream for new observational data, extend the local products and the obs catalog."))
    parser.add_argument("--version", action="version", version=__version__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", help="suite configuration (default: scripts/config.yaml)")
    common.add_argument("-m", "--machine", help="machine of catalogs/obs/machine.yaml (default: from AQUA config)")
    common.add_argument("-o", "--output-root", help="root of the products (default: DVC_PATH of the machine)")
    common.add_argument("-w", "--workdir", help="directory for downloads, cache and state")
    common.add_argument("-l", "--loglevel", default="INFO", help="logging level (default: INFO)")
    sub = parser.add_subparsers(dest="command", required=True)
    target_help = "datasets to process, optionally dataset:product (default: all enabled)"

    sub.add_parser("list", parents=[common], help="list datasets and products")
    p = sub.add_parser("check", parents=[common], help="compare local products with upstream (no download)")
    p.add_argument("targets", nargs="*", help=target_help)
    p = sub.add_parser("update", parents=[common], help="fetch, process and extend the products")
    p.add_argument("targets", nargs="*", help=target_help)
    p.add_argument("--mode", choices=MODES,
                   help="append to the local product or replace it (default: append if it exists)")
    p.add_argument("-s", "--start", type=month_arg, metavar="YYYYMM",
                   help="first month (replace only; default: dataset start year)")
    p.add_argument("-e", "--end", type=month_arg, metavar="YYYYMM",
                   help="last month, error if not available upstream (default: latest available)")
    p.add_argument("-n", "--dry-run", action="store_true", help="only report what would be done")
    p.add_argument("--catalog", action=argparse.BooleanOptionalAction, default=None,
                   help="edit the catalog yaml after the update (default: update_catalog in config.yaml)")
    p = sub.add_parser("catalog", parents=[common], help="align catalog yaml with the products on disk")
    p.add_argument("targets", nargs="*", help=target_help)
    p.add_argument("-n", "--dry-run", action="store_true", help="only show the edits")
    return parser


def enabled_datasets(settings, targets):
    selection = parse_targets(targets) if targets else {
        name: None for name in ObsDataset.registry
        if settings.dataset_options(name).get("enabled", True)}
    return [(ObsDataset.registry[name](settings), products) for name, products in selection.items()]


def cmd_list(settings, args):
    for name, cls in sorted(ObsDataset.registry.items()):
        ds = cls(settings)
        enabled = settings.dataset_options(name).get("enabled", True)
        print(f"{name:10s} {'enabled ' if enabled else 'disabled'} {cls.description} "
              f"[modes: {', '.join(cls.modes)}]")
        for p in ds.products():
            flag = " (frozen)" if p.frozen else ""
            print(f"    {p.key:12s} {ds.product_dir(p) / p.template}{flag}")
    return 0


def cmd_check(settings, args):
    rows = []
    for ds, products in enabled_datasets(settings, args.targets):
        rows += ds.check(products)
    print(f"{'dataset':10s} {'product':12s} {'status':10s} {'local':18s} upstream")
    for s in rows:
        print(f"{s.dataset:10s} {s.product:12s} {s.action:10s} {s.local_range:18s} {s.remote}"
              + (f"  [{s.message}]" if s.message else ""))
    return 1 if any(s.action == "error" for s in rows) else 0


def cmd_update(settings, args):
    failed = False
    update_catalog = settings.update_catalog if args.catalog is None else args.catalog
    for ds, products in enabled_datasets(settings, args.targets):
        try:
            results = ds.update(products, mode=args.mode, start=args.start, end=args.end,
                                dry_run=args.dry_run, update_catalog=update_catalog)
        except Exception as exc:  # keep going with the other datasets
            log.error("%s failed: %s", ds.name, exc, exc_info=log.isEnabledFor(logging.DEBUG))
            failed = True
            continue
        for r in results:
            print(f"== {r.dataset}:{r.product} {r.mode} {r.message}".rstrip())
            if r.error:
                failed = True
                print(f"   ERROR    : {r.error}")
            if r.output:
                print(f"   new file : {r.output}")
            if r.obsolete:
                print(f"   obsolete : {r.obsolete} (remove after dvc add)")
            for edit in r.edits:
                print(f"   catalog  : {edit}")
            if r.output and not update_catalog:
                print(f"   catalog  : not edited, run `aqua-obs catalog {r.dataset}:{r.product}` or use --catalog")
            if r.output:
                print(f"   then     : dvc add the tracked directory of {r.output.parent.name} "
                      "in aqua-dvc, dvc push -r ecmwf_climatedt, dvc pull on each machine")
    return 1 if failed else 0


def cmd_catalog(settings, args):
    for ds, products in enabled_datasets(settings, args.targets):
        for product in ds.products(products):
            local = ds.find_local(product)
            if local is None or not product.catalog:
                continue
            edits = ds.sync_catalog(product, local, dry_run=args.dry_run)
            for edit in edits:
                print(edit)
            if not edits:
                print(f"{ds.name}:{product.key} in sync with {local.name}")
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=args.loglevel.upper(), format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    try:
        settings = load_settings(args.config, args.machine, args.output_root, args.workdir)
    except ConfigError as exc:
        sys.exit(f"configuration error: {exc}")
    log.info("machine=%s output_root=%s workdir=%s", settings.machine, settings.output_root, settings.workdir)
    command = {"list": cmd_list, "check": cmd_check, "update": cmd_update, "catalog": cmd_catalog}
    sys.exit(command[args.command](settings, args))

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
LOGLEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def parse_targets(targets):
    """Targets follow the obs catalog: MODEL, MODEL:exp or MODEL:exp:source (model names are
    case-insensitive) -> {dataset: [exp or exp:source selectors] or None for all}."""
    names = {name.lower(): name for name in ObsDataset.registry}
    selection = {}
    for target in targets:
        model, _, product = target.partition(":")
        name = names.get(model.lower())
        if name is None:
            raise SystemExit(f"unknown dataset '{model}', available: {', '.join(sorted(ObsDataset.registry))}")
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


def add_common_options(parser, default):
    parser.add_argument("-c", "--config", default=default,
                        help="suite configuration (default: scripts/config.yaml)")
    parser.add_argument("-m", "--machine", default=default,
                        help="machine of catalogs/obs/machine.yaml (default: from AQUA config)")
    parser.add_argument("-o", "--output-root", default=default,
                        help="root of the products (default: DVC_PATH of the machine)")
    parser.add_argument("-w", "--workdir", default=default, help="directory for downloads, cache and state")
    parser.add_argument("-l", "--loglevel", default=default, type=str.upper, choices=LOGLEVELS,
                        help="logging level of aqua-obs (default: INFO); DEBUG also shows HTTP "
                             "requests and library warnings")


def setup_logging(level):
    """aqua-obs messages at `level`; third-party libraries and Python warnings only at DEBUG."""
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    log.setLevel(level)
    logging.captureWarnings(True)
    debug = level == "DEBUG"
    logging.getLogger("py.warnings").setLevel(logging.WARNING if debug else logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.DEBUG if debug else logging.WARNING)


def build_parser():
    parser = argparse.ArgumentParser(prog="aqua-obs", description=(
        "Check upstream for new observational data, extend the local products and the obs catalog."))
    parser.add_argument("--version", action="version", version=__version__)
    # common options are accepted before and after the subcommand (aqua-obs -l DEBUG check
    # or aqua-obs check -l DEBUG): the subcommand copies must not reset what was given before
    add_common_options(parser, argparse.SUPPRESS)
    parser.set_defaults(config=None, machine=None, output_root=None, workdir=None, loglevel="INFO")
    common = argparse.ArgumentParser(add_help=False)
    add_common_options(common, argparse.SUPPRESS)
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
        print(f"{name} ({'enabled' if enabled else 'disabled'}): {cls.description} "
              f"[modes: {', '.join(cls.modes)}]")
        for p in ds.products():
            flag = " (frozen)" if p.frozen else ""
            files = f", files: {', '.join(p.file_keys)}" if p.files else ""
            print(f"    {name}:{p.key}{flag}  [dvc: datasets/{p.dvc}{files}]")
            print(f"        {ds.product_dir(p) / p.template}")
    return 0


def cmd_check(settings, args):
    rows = []
    for ds, products in enabled_datasets(settings, args.targets):
        rows += ds.check(products)
    width = max([len(f"{s.dataset}:{s.product}") for s in rows] + [7])
    print(f"{'product':{width}s} {'status':10s} {'local':18s} upstream")
    for s in rows:
        print(f"{s.dataset + ':' + s.product:{width}s} {s.action:10s} {s.local_range:18s} {s.remote}"
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
            for line in r.details:
                print(f"   {line}")
            for path in r.outputs:
                print(f"   new file : {path}")
            for path in r.obsolete:
                print(f"   obsolete : {path} (remove after dvc add)")
            for edit in r.edits:
                print(f"   catalog  : {edit}")
            if r.outputs and not update_catalog:
                print(f"   catalog  : not edited, run `aqua-obs catalog {r.dataset}:{r.product}` or use --catalog")
            if r.outputs and r.dvc:
                print(f"   then     : in aqua-dvc, dvc add datasets/{r.dvc} && dvc push -r ecmwf_climatedt; "
                      "dvc pull on each machine")
    return 1 if failed else 0


def cmd_catalog(settings, args):
    for ds, products in enabled_datasets(settings, args.targets):
        for product in ds.products(products):
            local = ds.find_local(product)
            if not local or not product.catalog:
                continue
            ds.local_range(product, local)  # all files must cover the same months
            edits = ds.sync_catalog(product, list(local.values()), dry_run=args.dry_run)
            for edit in edits:
                print(edit)
            if not edits:
                print(f"{ds.name}:{product.key} in sync with {', '.join(p.name for p in local.values())}")
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    setup_logging(args.loglevel)
    try:
        settings = load_settings(args.config, args.machine, args.output_root, args.workdir)
    except ConfigError as exc:
        sys.exit(f"configuration error: {exc}")
    log.info("machine=%s output_root=%s workdir=%s", settings.machine, settings.output_root, settings.workdir)
    command = {"list": cmd_list, "check": cmd_check, "update": cmd_update, "catalog": cmd_catalog}
    sys.exit(command[args.command](settings, args))

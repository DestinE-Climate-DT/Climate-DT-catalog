"""Base class of the observational datasets.

A dataset declares its products and implements three hooks:

- remote_info(product): cheap look at upstream (no data download) for `check`;
- fetch(product, start, end): download the raw data covering the requested months;
- build(product, raw, start, end, template): an xarray Dataset of the processed months.

The base class turns them into two update modes, each restricted to [start, end] months:

- append: extend the existing product after its last month (start must be that month + 1);
- replace: rebuild the product from start (default: the dataset start year).

Requested months that upstream does not provide are an error and nothing is written.
Products are written as <name>_<YYYYMM>-<YYYYMM>; existing files are never modified.
Subclasses register themselves by `name` in ObsDataset.registry.
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import catalog, io
from .fetch import DownloadError, Fetcher
from .state import State
from .timeaxis import month_range, month_token, monthly_gaps, select_months

log = logging.getLogger(__name__)

MODES = ("append", "replace")


class UpdateError(RuntimeError):
    """The requested update cannot be done."""


@dataclass
class CatalogEntry:
    """A source of the obs catalog whose date range follows a product."""
    yaml: str                      # relative to catalog/<dataset name>/
    source: str
    fields: tuple = ("urlpath", "description")


@dataclass
class Product:
    """A product follows the obs catalog: the data of source `source` of experiment `exp` of the
    dataset (catalog model), e.g. EN4 v4.2.2 monthly-netcdf. Its key is "exp:source".

    It is a single file, or several files covering the same months when `files` maps file keys
    to their variables; the template then holds a {file} placeholder (e.g. {file}-EN4-...).
    """
    exp: str
    source: str
    template: str                  # file name with {start}, {end} and optionally {file}
    subdir: str                    # relative to output_root (= DVC_PATH layout)
    catalog: list = field(default_factory=list)
    frozen: bool = False           # never updated (kept for reference)
    params: dict = field(default_factory=dict)
    files: dict | None = None      # {file key: [variables]} for products split in several files
    dvc: str | None = None         # aqua-dvc pointer under datasets/ (default: <MODEL>/<dir>)

    def __post_init__(self):
        if self.dvc is None:
            self.dvc = "/".join(Path(self.subdir).parts[:2])

    @property
    def key(self):
        return f"{self.exp}:{self.source}"

    def selected_by(self, selector):
        """True if selector is the experiment or experiment:source of the product."""
        return selector in (self.exp, self.key)

    @property
    def file_keys(self):
        return list(self.files) if self.files else [""]

    def filename(self, start, end, file=""):
        return self.template.format(start=month_token(start), end=month_token(end), file=file)

    def match(self, name, file=""):
        """(start, end) tokens if name matches the template (YYYYMM, or YYYY for legacy files)."""
        parts = re.split(r"(\{start\}|\{end\})", self.template.replace("{file}", file))
        pattern = "".join({"{start}": r"(?P<start>\d{4}(?:\d{2})?)",
                           "{end}": r"(?P<end>\d{4}(?:\d{2})?)"}.get(p, re.escape(p)) for p in parts)
        m = re.fullmatch(pattern, name)
        return (m["start"], m["end"]) if m else None


@dataclass
class Remote:
    """What upstream offers, as far as can be known without downloading data."""
    last: pd.Period | None = None  # last month available, if known
    exact: bool = True             # False if `last` is only a lower bound
    text: str = ""                 # human readable summary
    signature: dict | None = None  # ETag/Last-Modified/size of a single upstream file


@dataclass
class Status:
    """Comparison between the local product and upstream."""
    dataset: str
    product: str
    action: str                    # up-to-date | new data | changed | unknown | missing | frozen | error
    local: dict = field(default_factory=dict)
    first: pd.Period | None = None
    last: pd.Period | None = None
    remote: str = ""
    message: str = ""

    @property
    def local_range(self):
        return f"{self.first}..{self.last}" if self.first is not None else ""


@dataclass
class Result:
    """Outcome of an update."""
    dataset: str
    product: str
    mode: str = ""
    outputs: list = field(default_factory=list)
    obsolete: list = field(default_factory=list)
    edits: list = field(default_factory=list)
    message: str = ""
    error: str = ""
    details: list = field(default_factory=list)  # dry run: what would be done
    dvc: str = ""                  # aqua-dvc pointer of the product


class ObsDataset(ABC):
    """Common machinery: products, local discovery, check/update, catalog sync."""

    name: str = None               # model name in the obs catalog (catalog/<name>/)
    description: str = ""
    modes: tuple = MODES
    start_year: int = 1979
    complete_years: bool = False   # by default extend only up to the last complete year
    registry: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.name:
            ObsDataset.registry[cls.name] = cls

    def __init__(self, settings):
        self.settings = settings
        self.options = settings.dataset_options(self.name)
        self.workdir = Path(settings.workdir) / self.name
        self.fetcher = Fetcher(retries=settings.retries, timeout=settings.timeout)
        self.state = State(settings.workdir, self.name)

    # ------------------------------------------------------------------ hooks
    @abstractmethod
    def all_products(self):
        """All products of the dataset (list of Product)."""

    @abstractmethod
    def remote_info(self, product):
        """Remote summary of product (no data download)."""

    @abstractmethod
    def fetch(self, product, start, end):
        """Download the raw data for months start..end (end None = all available).
        Return a handle passed to build()."""

    @abstractmethod
    def build(self, product, raw, start, end, template=None):
        """Processed monthly Dataset covering at least start..end where available.

        template is the existing product (or None): take grid and layout from it."""

    def fetch_plan(self, product, start, end):
        """Lines describing what fetch() would download (dry run). Optional."""
        return []

    # ------------------------------------------------------------------ products
    def products(self, selected=None):
        """Products enabled in the config, optionally restricted to experiments or exp:source."""
        enabled = self.options.get("products")
        prods = [p for p in self.all_products()
                 if enabled is None or p.frozen or any(p.selected_by(s) for s in enabled)]
        if selected:
            unknown = [s for s in selected if not any(p.selected_by(s) for p in prods)]
            if unknown:
                raise ValueError(f"{self.name}: unknown or disabled products {unknown}, "
                                 f"available: {', '.join(p.key for p in prods)}")
            prods = [p for p in prods if any(p.selected_by(s) for s in selected)]
        return prods

    def product_dir(self, product):
        return Path(self.settings.output_root) / product.subdir

    def find_local(self, product):
        """Current local product as {file key: path}, for each file the matching one with the
        latest end; {} if there is none."""
        folder = self.product_dir(product)
        if not folder.is_dir():
            return {}
        local = {}
        for key in product.file_keys:
            found = []
            for f in folder.iterdir():
                if f.name.endswith((".tmp", ".part")) or not (m := product.match(f.name, key)):
                    continue
                start, end = m
                found.append((end.ljust(6, "9"), start, f))  # YYYY files end in December
            if found:
                local[key] = max(found)[2]
        return local

    def local_range(self, product, local):
        """(first, last) month of the local product; all its files must cover the same months."""
        missing = [k for k in product.file_keys if k not in local]
        if missing:
            raise UpdateError(f"incomplete local product in {self.product_dir(product)}: "
                              f"no file for {', '.join(missing)}")
        ranges = {}
        for key, path in local.items():
            with io.open_product(path) as ds:
                ranges[key] = month_range(ds)
        if len(set(ranges.values())) > 1:
            detail = ", ".join(f"{k or 'file'} {a}..{b}" for k, (a, b) in ranges.items())
            raise UpdateError(f"local files cover different months: {detail}")
        return next(iter(ranges.values()))

    def output_paths(self, product, first, last):
        return {key: self.product_dir(product) / product.filename(first, last, key)
                for key in product.file_keys}

    def split(self, product, ds, key):
        """Variables of ds for one file of the product (all of them for single-file products):
        the variables listed for the other files are dropped, shared ones (bounds) are kept."""
        if not product.files:
            return ds
        others = {v for k, variables in product.files.items() if k != key for v in variables}
        return ds.drop_vars([v for v in ds.data_vars if v in others])

    def default_start(self):
        return pd.Period(f"{int(self.options.get('start_year', self.start_year))}-01", freq="M")

    def complete_only(self):
        return bool(self.options.get("complete_years", self.complete_years))

    # ------------------------------------------------------------------ check
    def check(self, selected=None):
        statuses = []
        for product in self.products(selected):
            try:
                statuses.append(self.check_product(product))
            except Exception as exc:  # report and continue with the other products
                log.debug("check failed", exc_info=True)
                statuses.append(Status(self.name, product.key, "error", message=str(exc)))
        return statuses

    def check_product(self, product):
        local = self.find_local(product)
        status = Status(self.name, product.key, "missing", local=local)
        if local:
            status.first, status.last = self.local_range(product, local)
        elif product.dvc:
            status.message = f"pull it with: dvc pull datasets/{product.dvc}.dvc"
        if product.frozen:
            status.action = "frozen"
            return status
        remote = self.remote_info(product)
        status.remote = remote.text
        if not local:
            return status
        last = remote.last
        if last is not None and self.complete_only() and last.month != 12:
            last = pd.Period(f"{last.year - 1}-12", freq="M")
        if last is not None:
            status.action = "new data" if last > status.last else "up-to-date"
            if status.action == "new data":
                status.message = f"up to {last}"
        elif remote.signature is not None:
            status.action = self._signature_status(product, remote.signature, local)
        else:
            status.action = "unknown"
        return status

    def _signature_status(self, product, signature, local):
        """Compare upstream with the version recorded at the last update made here; without a
        record (e.g. a product pulled from DVC) the status is unknown."""
        stored = self.state.get(product.key, "signature")
        if not stored:
            return "unknown"
        same = all(stored.get(k) == signature.get(k) for k in ("etag", "last_modified", "size"))
        return "up-to-date" if same else "changed"

    # ------------------------------------------------------------------ update
    def plan(self, product, mode=None, start=None, end=None):
        """Resolve mode and month range of an update: (mode, local, start, end)."""
        local = self.find_local(product)
        mode = mode or ("append" if local else "replace")
        if mode not in self.modes:
            raise UpdateError(f"{self.name} does not support mode '{mode}' (only {', '.join(self.modes)})")
        if mode == "append":
            if not local:
                hint = f" (dvc pull datasets/{product.dvc}.dvc)" if product.dvc else ""
                raise UpdateError(f"no local product to append to in {self.product_dir(product)}{hint}: "
                                  "pull it or use --mode replace")
            following = self.local_range(product, local)[1] + 1
            if start is not None and start != following:
                raise UpdateError(f"append continues from {following} (local product ends one month "
                                  f"before), --start {month_token(start)} is not allowed")
            start = following
        else:
            start = start or self.default_start()
        if end is not None and end < start:
            raise UpdateError(f"--end {month_token(end)} is before the first month to process ({start})")
        return mode, local, start, end

    def update(self, selected=None, mode=None, start=None, end=None, dry_run=False, update_catalog=False):
        results = []
        with self._lock():
            for product in self.products(selected):
                if product.frozen:
                    results.append(Result(self.name, product.key, message="frozen"))
                    continue
                result = Result(self.name, product.key, dvc=product.dvc or "")
                results.append(result)
                try:
                    result.mode, local, start_, end_ = self.plan(product, mode, start, end)
                    if dry_run:
                        result.message = "(dry run)"
                        reason = "--mode" if mode else ("local product exists" if local else "no local product")
                        result.details = self.describe(product, result.mode, reason, local, start_, end_,
                                                       update_catalog)
                        continue
                    result.outputs = self.update_product(product, result.mode, local, start_, end_)
                except (UpdateError, DownloadError, io.CompatibilityError, FileExistsError) as exc:
                    result.error = str(exc)
                    continue
                self.state.save()
                if not result.outputs:
                    result.message = "nothing new upstream"
                    continue
                for path in result.outputs:
                    self.validate(path)
                result.obsolete = [p for p in local.values() if p not in result.outputs]
                if update_catalog:
                    result.edits = self.sync_catalog(product, result.outputs)
        return results

    def describe(self, product, mode, reason, local, start, end, update_catalog=False):
        """Dry run: what an update with this plan would do, as printable lines."""
        lines = [f"mode     : {mode} ({reason})"]
        first_local = None
        if local:
            first_local, last_local = self.local_range(product, local)
            for path in local.values():
                lines.append(f"local    : {path} ({first_local}..{last_local})")
        else:
            lines.append(f"local    : none in {self.product_dir(product)}")
            if product.dvc:
                lines.append(f"           to append to the published version: dvc pull datasets/{product.dvc}.dvc")
        remote = self.remote_info(product)
        lines.append(f"upstream : {remote.text}")

        target = end
        if end is None and remote.last is not None and remote.exact:
            target = remote.last
            if self.complete_only() and target.month != 12:
                target = pd.Period(f"{target.year - 1}-12", freq="M")
        months = f"{start}..{end}" if end is not None else f"{start}..latest available"
        if end is None:
            months += f" (expected {target})" if target is not None else " (known only after download)"
            if self.complete_only():
                months += ", complete years only"
        lines.append(f"months   : {months}")
        if end is not None and remote.last is not None and end > remote.last:
            lines.append(f"WARNING  : upstream {'has' if remote.exact else 'surely has'} data up to "
                         f"{remote.last}: {'the update will fail' if remote.exact else 'checked after download'}")
        lines += [f"download : {line}" for line in self.fetch_plan(product, start, end)]

        if target is not None and target < start:
            lines.append("output   : none, nothing new expected upstream")
            return lines
        if target is None:
            lines.append("output   : names known after download")
            return lines
        first = first_local if mode == "append" else start
        outputs = self.output_paths(product, first, target)
        for key, output in outputs.items():
            if mode == "append":
                how = f"{local[key].name} + {start}..{target}, rewritten"
            else:
                how = "new" + (", local product as grid template" if local else "")
            lines.append(f"output   : {output} ({how})")
        for path in local.values():
            if path not in outputs.values():
                lines.append(f"obsolete : {path.name} (kept, remove after dvc add)")
        if product.dvc:
            lines.append(f"dvc      : dvc add datasets/{product.dvc} && dvc push")
        if not product.catalog:
            return lines
        if not update_catalog:
            lines.append("catalog  : not edited (use --catalog)")
            return lines
        for edit in self.sync_catalog(product, list(outputs.values()), dry_run=True):
            lines.append(f"catalog  : {str(edit).replace(chr(10), chr(10) + ' ' * 11)}")
        return lines

    def update_product(self, product, mode, local, start, end):
        """Run the update; return the list of written files ([] if nothing new)."""
        remote = self.remote_info(product)
        raw = self.fetch(product, start, end)
        templates = {key: io.open_product(path) for key, path in local.items()}
        try:
            grid = next(iter(templates.values()), None)
            new = self.build(product, raw, start, end, template=grid)
            new = select_months(new, start, end)
            if end is None and self.complete_only() and new.sizes["time"]:
                last = month_range(new)[1]
                if last.month != 12:
                    new = select_months(new, None, pd.Period(f"{last.year - 1}-12", freq="M"))
            if not new.sizes["time"]:
                if end is not None:
                    raise UpdateError(f"{self.name} {product.key}: no data upstream for {start}..{end}")
                return []
            first, last = month_range(new)
            if first != start:
                raise UpdateError(f"{self.name} {product.key}: upstream data start at {first}, "
                                  f"{start} requested")
            if end is not None and last != end:
                raise UpdateError(f"{self.name} {product.key}: upstream data available only up to "
                                  f"{last}, {end} requested")
            outputs = self._write(product, mode, templates, new)
        finally:
            for ds in templates.values():
                ds.close()
        self.state.set(product.key, mode=mode, start=str(start), end=str(last),
                       outputs=[str(p) for p in outputs], signature=remote.signature)
        return outputs

    def _write(self, product, mode, templates, new):
        first_new, last_new = month_range(new)
        msg = f"aqua-obs {self.name}: {mode} {first_new}..{last_new}"
        first = month_range(next(iter(templates.values())))[0] if mode == "append" else first_new
        paths = self.output_paths(product, first, last_new)
        # build everything before writing, so that a compatibility error leaves no partial product
        datasets = {}
        for key, path in paths.items():
            part = self.split(product, new, key)
            template = templates.get(key)
            if mode == "append":
                datasets[key] = io.append_time(template, part)
            else:
                datasets[key] = io.like_template(template, part) if template is not None else part
        return [io.write_netcdf(io.add_history(datasets[key], msg), path) for key, path in paths.items()]

    def validate(self, path):
        """Re-open the written product and check its monthly time axis."""
        with io.open_product(path) as ds:
            problems = monthly_gaps(ds["time"].values)
        if problems:
            raise UpdateError(f"{path}: {'; '.join(problems)}")

    # ------------------------------------------------------------------ catalog
    def catalog_path(self, entry):
        return Path(self.settings.catalog_root) / "catalog" / self.name / entry.yaml

    def sync_catalog(self, product, paths, dry_run=False):
        """Align the date ranges of the catalog entries of product with the names of its files."""
        start, end = product.match(Path(paths[0]).name, product.file_keys[0])
        edits = []
        for entry in product.catalog:
            edits += catalog.sync_range(self.catalog_path(entry), entry.source, start, end,
                                        fields=entry.fields, dry_run=dry_run)
        return edits

    # ------------------------------------------------------------------ helpers
    @contextmanager
    def _lock(self):
        lock = Path(self.settings.workdir) / f"{self.name}.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise UpdateError(f"{lock} exists: another update of {self.name} is running "
                              "(remove the file if it is stale)") from exc
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            lock.unlink(missing_ok=True)

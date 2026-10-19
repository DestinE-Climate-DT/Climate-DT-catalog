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
from email.utils import parsedate_to_datetime
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
    yaml: str                      # relative to catalog/<catalog_dir>/
    source: str
    fields: tuple = ("urlpath", "description")


@dataclass
class Product:
    """One output file (or zarr store) of a dataset."""
    key: str
    template: str                  # file name with {start} and {end}
    subdir: str                    # relative to output_root
    catalog: list = field(default_factory=list)
    frozen: bool = False           # never updated (kept for reference)
    params: dict = field(default_factory=dict)

    @property
    def is_zarr(self):
        return self.template.endswith(".zarr")

    def filename(self, start, end):
        return self.template.format(start=month_token(start), end=month_token(end))

    def match(self, name):
        """(start, end) tokens if name matches the template (YYYYMM, or YYYY for legacy files)."""
        parts = re.split(r"(\{start\}|\{end\})", self.template)
        pattern = "".join({"{start}": r"(?P<start>\d{4}(?:\d{2})?)",
                           "{end}": r"(?P<end>\d{4}(?:\d{2})?)"}.get(p, re.escape(p)) for p in parts)
        m = re.fullmatch(pattern, name)
        return (m["start"], m["end"]) if m else None


@dataclass
class Remote:
    """What upstream offers, as far as can be known without downloading data."""
    last: pd.Period | None = None  # last month available, if known
    text: str = ""                 # human readable summary
    signature: dict | None = None  # ETag/Last-Modified/size of a single upstream file


@dataclass
class Status:
    """Comparison between the local product and upstream."""
    dataset: str
    product: str
    action: str                    # up-to-date | new data | changed | unknown | missing | frozen | error
    local: Path | None = None
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
    output: Path | None = None
    obsolete: Path | None = None
    edits: list = field(default_factory=list)
    message: str = ""
    error: str = ""


class ObsDataset(ABC):
    """Common machinery: products, local discovery, check/update, catalog sync."""

    name: str = None
    catalog_dir: str = None
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

    # ------------------------------------------------------------------ products
    def products(self, selected=None):
        """Products enabled in the config, optionally filtered by key."""
        enabled = self.options.get("products")
        prods = [p for p in self.all_products() if enabled is None or p.key in enabled or p.frozen]
        if selected:
            unknown = set(selected) - {p.key for p in prods}
            if unknown:
                raise ValueError(f"{self.name}: unknown or disabled products {sorted(unknown)}")
            prods = [p for p in prods if p.key in selected]
        return prods

    def product_dir(self, product):
        return Path(self.settings.output_root) / product.subdir

    def find_local(self, product):
        """Current local product: the matching file with the latest end, or None."""
        folder = self.product_dir(product)
        if not folder.is_dir():
            return None
        found = []
        for f in folder.iterdir():
            if f.name.endswith((".tmp", ".part")) or not (m := product.match(f.name)):
                continue
            start, end = m
            found.append((end.ljust(6, "9"), start, f))  # YYYY files end in December
        return max(found)[2] if found else None

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
        if local is not None:
            with io.open_product(local) as ds:
                status.first, status.last = month_range(ds)
        if product.frozen:
            status.action = "frozen"
            return status
        remote = self.remote_info(product)
        status.remote = remote.text
        if local is None:
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
        stored = self.state.get(product.key, "signature")
        if stored:
            same = all(stored.get(k) == signature.get(k) for k in ("etag", "last_modified", "size"))
            return "up-to-date" if same else "changed"
        modified = signature.get("last_modified")
        if modified and parsedate_to_datetime(modified).timestamp() <= Path(local).stat().st_mtime:
            return "up-to-date"
        return "changed"

    # ------------------------------------------------------------------ update
    def plan(self, product, mode=None, start=None, end=None):
        """Resolve mode and month range of an update: (mode, local, start, end)."""
        local = self.find_local(product)
        mode = mode or ("append" if local is not None else "replace")
        if mode not in self.modes:
            raise UpdateError(f"{self.name} does not support mode '{mode}' (only {', '.join(self.modes)})")
        if mode == "append":
            if local is None:
                raise UpdateError(f"no local product to append to in {self.product_dir(product)}: "
                                  "use --mode replace")
            with io.open_product(local) as ds:
                following = month_range(ds)[1] + 1
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
                result = Result(self.name, product.key)
                results.append(result)
                try:
                    result.mode, local, start_, end_ = self.plan(product, mode, start, end)
                    if dry_run:
                        result.message = f"(dry run) {start_} to {end_ or 'latest available'}"
                        continue
                    result.output = self.update_product(product, result.mode, local, start_, end_)
                except (UpdateError, DownloadError, io.CompatibilityError, FileExistsError) as exc:
                    result.error = str(exc)
                    continue
                self.state.save()
                if result.output is None:
                    result.message = "nothing new upstream"
                else:
                    self.validate(result.output)
                    if local is not None and Path(local) != Path(result.output):
                        result.obsolete = local
                    if update_catalog:
                        result.edits = self.sync_catalog(product, result.output)
        return results

    def update_product(self, product, mode, local, start, end):
        remote = self.remote_info(product)
        raw = self.fetch(product, start, end)
        template = io.open_product(local) if local is not None else None
        try:
            new = self.build(product, raw, start, end, template=template)
            new = select_months(new, start, end)
            if end is None and self.complete_only() and new.sizes["time"]:
                last = month_range(new)[1]
                if last.month != 12:
                    new = select_months(new, None, pd.Period(f"{last.year - 1}-12", freq="M"))
            if not new.sizes["time"]:
                if end is not None:
                    raise UpdateError(f"{self.name} {product.key}: no data upstream for {start}..{end}")
                return None
            first, last = month_range(new)
            if first != start:
                raise UpdateError(f"{self.name} {product.key}: upstream data start at {first}, "
                                  f"{start} requested")
            if end is not None and last != end:
                raise UpdateError(f"{self.name} {product.key}: upstream data available only up to "
                                  f"{last}, {end} requested")
            output = self._write(product, mode, local, template, new)
        finally:
            if template is not None:
                template.close()
        self.state.set(product.key, mode=mode, start=str(start), end=str(last), output=str(output),
                       signature=remote.signature)
        return output

    def _write(self, product, mode, local, template, new):
        msg = f"aqua-obs {self.name}: {mode} {month_range(new)[0]}..{month_range(new)[1]}"
        chunks = product.params.get("chunks")
        if mode == "append":
            first = month_range(template)[0]
            output = self.product_dir(product) / product.filename(first, month_range(new)[1])
            if product.is_zarr:
                return io.extend_zarr(local, new, output, chunks=chunks)
            return io.write_netcdf(io.add_history(io.append_time(template, new), msg), output)
        output = self.product_dir(product) / product.filename(*month_range(new))
        if template is not None:
            new = io.like_template(template, new)
        if product.is_zarr:
            return io.write_zarr(io.add_history(new, msg), output, chunks=chunks)
        return io.write_netcdf(io.add_history(new, msg), output)

    def validate(self, path):
        """Re-open the written product and check its monthly time axis."""
        with io.open_product(path) as ds:
            problems = monthly_gaps(ds["time"].values)
        if problems:
            raise UpdateError(f"{path}: {'; '.join(problems)}")

    # ------------------------------------------------------------------ catalog
    def catalog_path(self, entry):
        return Path(self.settings.catalog_root) / "catalog" / self.catalog_dir / entry.yaml

    def sync_catalog(self, product, path, dry_run=False):
        """Align the date ranges of the catalog entries of product with the file name of path."""
        start, end = product.match(Path(path).name)
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

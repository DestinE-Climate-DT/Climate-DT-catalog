"""HTTP helpers: robust downloads with retry/resume, HEAD probes and directory listings."""

import gzip
import logging
import re
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

CHUNK = 1 << 20


class DownloadError(RuntimeError):
    """Raised when a file cannot be downloaded or fails validation."""


def make_session(retries=5, backoff=2.0):
    """Session retrying on connection errors and 5xx/429 responses."""
    session = requests.Session()
    retry = Retry(total=retries, backoff_factor=backoff,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET", "HEAD"))
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers["User-Agent"] = "aqua-obs"
    return session


class Fetcher:
    """Thin wrapper around a requests session with the operations used by the datasets."""

    def __init__(self, retries=5, timeout=60):
        self.session = make_session(retries)
        self.timeout = timeout

    def head(self, url):
        """Return a signature dict (etag, last_modified, size) or None if the URL does not exist."""
        resp = self.session.head(url, allow_redirects=True, timeout=self.timeout)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        size = resp.headers.get("Content-Length")
        return {"url": url,
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
                "size": int(size) if size is not None else None}

    def listing(self, url, pattern):
        """Return the regex matches found in the href targets of an HTML directory listing."""
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        regex = re.compile(pattern)
        hrefs = re.findall(r'href="([^"]+)"', resp.text)
        return [m for m in (regex.fullmatch(h) for h in hrefs) if m]

    def download(self, url, dest, validator=None, overwrite=False):
        """Download url to dest through a .part file, resuming partial downloads.

        The file is moved into place only after the optional validator(path) returned True.
        An existing valid dest is reused unless overwrite is True.
        """
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not overwrite:
            if validator is None or validator(dest):
                log.debug("Reusing %s", dest)
                return dest
            log.warning("Invalid local file %s, downloading again", dest)
        part = dest.with_name(dest.name + ".part")
        headers = {}
        if part.exists() and part.stat().st_size > 0:
            headers["Range"] = f"bytes={part.stat().st_size}-"
        with self.session.get(url, stream=True, headers=headers, timeout=self.timeout) as resp:
            if resp.status_code == 416:  # range not satisfiable: .part already complete
                pass
            elif resp.status_code == 404:
                raise DownloadError(f"{url} not found")
            else:
                resp.raise_for_status()
                log.info("Downloading %s", url)
                mode = "ab" if resp.status_code == 206 else "wb"
                with open(part, mode) as fh:
                    for chunk in resp.iter_content(CHUNK):
                        fh.write(chunk)
        if validator is not None and not validator(part):
            part.unlink()
            raise DownloadError(f"{url} downloaded but failed validation")
        part.replace(dest)
        return dest


# validators -----------------------------------------------------------------

def nonempty(path):
    """File exists and is not empty."""
    return Path(path).stat().st_size > 0


def gzip_size(expected):
    """Validator: gzip integrity and uncompressed size equal to expected bytes."""
    def _check(path):
        try:
            with gzip.open(path, "rb") as fh:
                n = 0
                while chunk := fh.read(CHUNK):
                    n += len(chunk)
        except (OSError, EOFError):
            return False
        return n == expected
    return _check


def file_size(expected):
    """Validator: file size equal to expected bytes."""
    return lambda path: Path(path).stat().st_size == expected


def netcdf_opens(path):
    """Validator: the file opens as netCDF."""
    import netCDF4
    try:
        netCDF4.Dataset(path).close()
    except OSError:
        return False
    return True


def gzip_multiple(unit):
    """Validator: gzip integrity and a non-empty uncompressed size multiple of unit bytes."""
    def _check(path):
        try:
            with gzip.open(path, "rb") as fh:
                n = 0
                while chunk := fh.read(CHUNK):
                    n += len(chunk)
        except (OSError, EOFError):
            return False
        return n > 0 and n % unit == 0
    return _check


def size_multiple(unit):
    """Validator: non-empty file size multiple of unit bytes."""
    def _check(path):
        n = Path(path).stat().st_size
        return n > 0 and n % unit == 0
    return _check

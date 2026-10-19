import functools
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from aqua_obs.config import Settings

CATALOG_ROOT = Path(__file__).resolve().parents[2]  # catalogs/obs


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture
def http_dir(tmp_path):
    """(directory, base_url) of a local HTTP server serving that directory."""
    root = tmp_path / "remote"
    root.mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def catalog_copy(tmp_path):
    """A copy of catalogs/obs (yaml only) that tests are free to modify."""
    dest = tmp_path / "obs"
    shutil.copytree(CATALOG_ROOT / "catalog", dest / "catalog",
                    ignore=shutil.ignore_patterns("*.ipynb", "scripts"))
    shutil.copy(CATALOG_ROOT / "machine.yaml", dest)
    return dest


@pytest.fixture
def settings(tmp_path, catalog_copy):
    return Settings(machine="test", output_root=tmp_path / "out", workdir=tmp_path / "work",
                    catalog_root=catalog_copy, retries=0, timeout=10)

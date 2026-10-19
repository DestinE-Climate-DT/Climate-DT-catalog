import gzip

import pytest

from aqua_obs.fetch import DownloadError, Fetcher, file_size, gzip_size


def test_download_and_reuse(http_dir, tmp_path):
    root, url = http_dir
    (root / "a.bin").write_bytes(b"x" * 100)
    fetcher = Fetcher(retries=0)
    dest = fetcher.download(f"{url}/a.bin", tmp_path / "dl" / "a.bin", validator=file_size(100))
    assert dest.read_bytes() == b"x" * 100
    assert not dest.with_name("a.bin.part").exists()
    (root / "a.bin").write_bytes(b"y" * 100)
    assert fetcher.download(f"{url}/a.bin", dest).read_bytes() == b"x" * 100  # reused
    assert fetcher.download(f"{url}/a.bin", dest, overwrite=True).read_bytes() == b"y" * 100


def test_download_invalid_and_missing(http_dir, tmp_path):
    root, url = http_dir
    (root / "a.bin").write_bytes(b"x" * 10)
    fetcher = Fetcher(retries=0)
    with pytest.raises(DownloadError, match="validation"):
        fetcher.download(f"{url}/a.bin", tmp_path / "a.bin", validator=file_size(11))
    assert not (tmp_path / "a.bin").exists() and not (tmp_path / "a.bin.part").exists()
    with pytest.raises(DownloadError, match="not found"):
        fetcher.download(f"{url}/missing.bin", tmp_path / "m.bin")


def test_gzip_validator(tmp_path):
    good = tmp_path / "g.gz"
    with gzip.open(good, "wb") as fh:
        fh.write(b"z" * 48)
    assert gzip_size(48)(good)
    assert not gzip_size(47)(good)
    bad = tmp_path / "b.gz"
    bad.write_bytes(b"not gzip")
    assert not gzip_size(48)(bad)


def test_head_and_listing(http_dir):
    root, url = http_dir
    for name in ("heff.H2020.gz", "heff.H2021", "other.txt"):
        (root / name).write_bytes(b"0" * 8)
    fetcher = Fetcher(retries=0)
    assert fetcher.head(f"{url}/heff.H2021")["size"] == 8
    assert fetcher.head(f"{url}/nothing") is None
    matches = fetcher.listing(f"{url}/", r"heff\.H(\d{4})(\.gz)?")
    assert sorted(int(m[1]) for m in matches) == [2020, 2021]

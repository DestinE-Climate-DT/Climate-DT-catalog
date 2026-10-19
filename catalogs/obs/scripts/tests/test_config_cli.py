from pathlib import Path

import pytest
import yaml

from aqua_obs import cli
from aqua_obs.config import ConfigError, load_settings


def write_config(tmp_path, catalog_copy, **extra):
    cfg = {"machine": "auto", "catalog_root": str(catalog_copy),
           "defaults": {"workdir": str(tmp_path / "work")}, **extra}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return path


def test_machine_from_machine_yaml(tmp_path, catalog_copy):
    settings = load_settings(write_config(tmp_path, catalog_copy), machine="levante")
    assert str(settings.output_root) == "/work/bk1580/aqua-dvc/datasets"
    assert settings.workdir == tmp_path / "work"


def test_overrides_and_errors(tmp_path, catalog_copy, monkeypatch):
    config = write_config(tmp_path, catalog_copy, machines={"laptop": {"output_root": "/data/obs"}})
    assert str(load_settings(config, machine="laptop").output_root) == "/data/obs"
    assert str(load_settings(config, machine="laptop", output_root="/x").output_root) == "/x"
    with pytest.raises(ConfigError, match="neither"):
        load_settings(config, machine="nowhere")
    with pytest.raises(ConfigError, match="no DVC_PATH"):
        load_settings(config, machine="lumi-e25.1")
    # auto: machine from the AQUA config
    aqua = tmp_path / "aqua"
    aqua.mkdir()
    (aqua / "config-aqua.yaml").write_text("machine: levante\n")
    monkeypatch.setenv("AQUA_CONFIG", str(aqua))
    assert load_settings(config).machine == "levante"


def test_cli_list_and_targets(tmp_path, catalog_copy, capsys):
    config = write_config(tmp_path, catalog_copy)
    with pytest.raises(SystemExit) as exc:
        cli.main(["list", "-c", str(config), "-m", "levante"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "psc" in out and "giomas" in out and "(frozen)" in out
    assert cli.parse_targets(["psc:piomas", "en4", "psc:giomas"]) == {"psc": ["piomas", "giomas"], "en4": None}
    with pytest.raises(SystemExit):
        cli.parse_targets(["nope"])


def test_machine_dataset_overrides(tmp_path, catalog_copy):
    config = write_config(tmp_path, catalog_copy,
                          datasets={"en4": {"start_year": 1950, "products": ["so", "zarr"]}},
                          machines={"laptop": {"output_root": "~/obs", "catalog_root": str(tmp_path / "cat"),
                                               "datasets": {"en4": {"start_year": 2024}}}})
    settings = load_settings(config, machine="laptop")
    assert settings.dataset_options("en4") == {"start_year": 2024, "products": ["so", "zarr"]}
    assert settings.catalog_root == tmp_path / "cat"
    assert str(settings.output_root).startswith(str(Path.home()))


def test_update_catalog_option(tmp_path, catalog_copy):
    config = write_config(tmp_path, catalog_copy, machines={"laptop": {"output_root": "/x", "update_catalog": True}})
    assert load_settings(config, machine="levante").update_catalog is False
    assert load_settings(config, machine="laptop").update_catalog is True
    args = cli.build_parser().parse_args(["update", "--no-catalog"])
    assert args.catalog is False
    assert cli.build_parser().parse_args(["update"]).catalog is None

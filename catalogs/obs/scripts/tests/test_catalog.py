from aqua_obs.catalog import current_range, sync_range


def changed_lines(before, after):
    return [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]


def test_berkeley_legacy_years_to_months(catalog_copy):
    path = catalog_copy / "catalog" / "BERKELEY-EARTH" / "aqua-filled.yaml"
    before = path.read_text()
    assert current_range(path, "r100-monthly") == ("1979", "2025")
    edits = sync_range(path, "r100-monthly", "197901", "202606")
    after = path.read_text()
    assert len(edits) == 2
    assert changed_lines(before, after) == [
        ("    description: Global Monthly Surface Temperature from Berkeley Earth (1979-2025) 1x1 deg"
         " - Beta product at 1x1 deg resolution",
         "    description: Global Monthly Surface Temperature from Berkeley Earth (1979-2026) 1x1 deg"
         " - Beta product at 1x1 deg resolution"),
        ("      urlpath: '{{DVC_PATH}}/BERKELEY-EARTH/aqua-filled/Berkeley-Earth_aqua-filled_1x1_1979-2025.nc'",
         "      urlpath: '{{DVC_PATH}}/BERKELEY-EARTH/aqua-filled/Berkeley-Earth_aqua-filled_1x1_197901-202606.nc'"),
    ]
    assert "1979-2024_v1.nc" in after  # other source untouched
    assert sync_range(path, "r100-monthly", "197901", "202606") == []  # idempotent


def test_en4_glob_and_anchor(catalog_copy):
    path = catalog_copy / "catalog" / "EN4" / "v4.2.2.yaml"
    before = path.read_text()
    sync_range(path, "monthly-netcdf", "195001", "202612")
    sync_range(path, "monthly-zarr", "195001", "202612")
    after = path.read_text()
    assert len(changed_lines(before, after)) == 4
    assert "'{{DVC_PATH}}/EN4/v4.2.2/netcdf/*EN4-195001-202612.nc'" in after
    assert "EN4.v422.195001-202612.clev.zarr" in after
    assert "from 1950 to 2026 in zarr format" in after
    assert "<<: *monthly-zarr" in after


def test_psc_list_urlpath_with_spaces(catalog_copy):
    path = catalog_copy / "catalog" / "PSC" / "piomas.yaml"
    before = path.read_text()
    assert len(sync_range(path, "monthly", "197901", "202603")) == 1
    after = path.read_text()
    assert "'{{ DVC_PATH }}/PSC/PIOMAS/sithick_r1i1p1_mon_197901-202603_GCCS360x120_curvgrid.nc'" in after
    assert len(changed_lines(before, after)) == 1


def test_dry_run(catalog_copy):
    path = catalog_copy / "catalog" / "PSC" / "giomas.yaml"
    before = path.read_text()
    assert len(sync_range(path, "monthly", "197901", "202612", dry_run=True)) == 1
    assert path.read_text() == before

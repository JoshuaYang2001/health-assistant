from inspect_cpap_sd import inspect_card


def test_inventory_does_not_read_or_change_card(tmp_path):
    root = tmp_path / "card"
    session = root / "P-Series" / "private-id" / "P0"
    session.mkdir(parents=True)
    record = session / "00000001.001"
    record.write_bytes(b"example contents")
    before = record.stat().st_mtime_ns
    found, counts = inspect_card(root)
    assert found
    assert counts[".001"] == 1
    assert record.read_bytes() == b"example contents"
    assert record.stat().st_mtime_ns == before


def test_ignores_symlinked_devices(tmp_path):
    root = tmp_path / "card"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "P-Series").symlink_to(outside, target_is_directory=True)
    assert inspect_card(root)[0] is False

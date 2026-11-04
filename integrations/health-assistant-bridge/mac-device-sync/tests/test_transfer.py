from uuid import uuid4

import pytest
import sync_glucose
from sync_glucose import check_server_url, decode_transfer


def packet(flags=0x06, seq=42, concentration=b"\x37\xc0", extra=b""):
    return (
        bytes([flags, seq, 0, 0xEA, 0x07, 11, 4, 9, 30, 0])
        + concentration
        + b"\x11"
        + extra
    ).hex()


def test_convert_and_deduplicate():
    transfer = {"device_id": str(uuid4()), "packets": [packet(), packet()]}
    records = decode_transfer(transfer, "Asia/Shanghai")
    assert len(records) == 1
    assert records[0].code == "15074-8"
    assert records[0].value == 5.5
    assert records[0].unit == "mmol/L"
    assert records[0].timestamp == "2026-11-04T01:30:00+00:00"
    assert len(records[0].external_id) == 64
    assert (
        decode_transfer(transfer, "Asia/Shanghai")[0].external_id
        == records[0].external_id
    )


def test_mass_unit_uses_matching_loinc():
    transfer = {
        "device_id": str(uuid4()),
        "packets": [packet(0x02, concentration=b"\x5a\xb0")],
    }
    record = decode_transfer(transfer, "UTC")[0]
    assert record.value == 90
    assert record.unit == "mg/dL"
    assert record.code == "2339-0"


def test_reject_ambiguous_or_unsafe_readings():
    device_id = str(uuid4())
    with pytest.raises(ValueError, match="conflicting"):
        decode_transfer(
            {
                "device_id": device_id,
                "packets": [packet(), packet(concentration=b"\x38\xc0")],
            },
            "UTC",
        )
    with pytest.raises(ValueError, match="sensor status"):
        decode_transfer(
            {"device_id": device_id, "packets": [packet(0x0E, extra=b"\x20\x00")]},
            "UTC",
        )
    with pytest.raises(ValueError, match="extra reading context"):
        decode_transfer({"device_id": device_id, "packets": [packet(0x16)]}, "UTC")


def test_server_url_requires_tls_except_loopback():
    check_server_url("http://127.0.0.1:8100")
    check_server_url("https://example.com")
    with pytest.raises(ValueError):
        check_server_url("http://192.168.1.2")
    with pytest.raises(ValueError):
        check_server_url("https://example.com/path")


def test_upload_remains_disabled_until_device_validation(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv", ["sync_glucose.py", "--timezone", "UTC", "--upload"]
    )
    monkeypatch.setattr(
        sync_glucose, "read_meter", lambda *_: pytest.fail("must not access meter")
    )
    assert sync_glucose.main() == 1
    assert "尚未完成实机验证" in capsys.readouterr().err

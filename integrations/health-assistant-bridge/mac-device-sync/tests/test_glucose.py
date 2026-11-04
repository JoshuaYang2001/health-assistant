from datetime import datetime, timezone
from decimal import Decimal

import pytest
from glucose import decode_measurement


def record(flags=0x06, concentration=b"\x37\xc0", extra=b""):
    return (
        bytes([flags, 42, 0, 0xEA, 0x07, 11, 4, 9, 30, 0])
        + extra
        + concentration
        + b"\x11"
    )


def test_mmol_and_tz():
    reading = decode_measurement(record(), "Asia/Shanghai")
    assert reading.sequence == 42
    assert reading.value == Decimal("5.5")
    assert reading.unit == "mmol/L"
    assert reading.measured_at == datetime(2026, 11, 4, 1, 30, tzinfo=timezone.utc)
    assert (reading.sample_type, reading.sample_location) == (1, 1)


def test_kg_per_l_to_mg_dl_and_signed_offset():
    reading = decode_measurement(record(0x03, b"\x5a\xb0", b"\xe2\xff"), "UTC")
    assert reading.value == Decimal(90)
    assert reading.unit == "mg/dL"
    assert reading.measured_at == datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)


def test_status_and_context_are_preserved():
    reading = decode_measurement(record(0x1E) + b"\x20\x00", "UTC")
    assert reading.sensor_status == 32
    assert reading.context_follows


@pytest.mark.parametrize(
    "data",
    [
        b"",
        record()[:-1],
        record(concentration=b"\xff\x07"),
        record(concentration=b"\x00\x00"),
        record(flags=0x80),
    ],
)
def test_reject_invalid_packets(data):
    with pytest.raises(ValueError):
        decode_measurement(data, "UTC")


def test_reject_nonexistent_or_ambiguous_clock():
    data = bytes([0x06, 1, 0, 0xEA, 0x07, 11, 1, 1, 30, 0]) + b"\x37\xc0\x11"
    with pytest.raises(ValueError, match="ambiguous"):
        decode_measurement(data, "America/New_York")

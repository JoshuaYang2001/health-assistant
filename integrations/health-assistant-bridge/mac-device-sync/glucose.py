"""Decode Bluetooth SIG Glucose Measurement records without device side effects."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class GlucoseReading:
    sequence: int
    measured_at: datetime
    value: Decimal
    unit: str
    sample_type: int
    sample_location: int
    sensor_status: int | None
    context_follows: bool


def _sfloat(data: bytes) -> Decimal:
    raw = int.from_bytes(data, "little")
    mantissa = raw & 0x0FFF
    if mantissa in (0x07FE, 0x07FF, 0x0800, 0x0801, 0x0802):
        raise ValueError("Glucose concentration is a special non-numeric value")
    if mantissa & 0x0800:
        mantissa -= 0x1000
    exponent = raw >> 12
    if exponent & 0x08:
        exponent -= 0x10
    return Decimal(mantissa) * (Decimal(10) ** exponent)


def decode_measurement(data: bytes, time_zone: str) -> GlucoseReading:
    """Decode a Glucose Measurement, requiring a numeric blood glucose sample.

    The device supplies a local wall time, with no zone. The caller must
    explicitly provide its IANA time zone and verify the meter clock.
    """
    if len(data) < 10:
        raise ValueError("Glucose measurement is truncated")
    flags = data[0]
    if flags & 0xE0:
        raise ValueError("Glucose measurement has unsupported flag bits")
    sequence = int.from_bytes(data[1:3], "little")
    year = int.from_bytes(data[3:5], "little")
    try:
        wall = datetime.fromisoformat(
            f"{year:04d}-{data[5]:02d}-{data[6]:02d}T{data[7]:02d}:{data[8]:02d}:{data[9]:02d}"
        )
    except ValueError as exc:
        raise ValueError("Glucose measurement has an invalid device time") from exc
    pos = 10
    if flags & 0x01:
        if len(data) < pos + 2:
            raise ValueError("Glucose measurement time offset is truncated")
        wall += timedelta(
            minutes=int.from_bytes(data[pos : pos + 2], "little", signed=True)
        )
        pos += 2
    if not flags & 0x02:
        raise ValueError("Glucose concentration is missing")
    if len(data) < pos + 3:
        raise ValueError("Glucose concentration is truncated")
    concentration = _sfloat(data[pos : pos + 2])
    if concentration <= 0:
        raise ValueError("Glucose concentration is not positive")
    sample = data[pos + 2]
    pos += 3
    unit = "mmol/L" if flags & 0x04 else "mg/dL"
    value = concentration * (Decimal(1000) if flags & 0x04 else Decimal(100000))
    status = None
    if flags & 0x08:
        if len(data) < pos + 2:
            raise ValueError("Glucose sensor status is truncated")
        status = int.from_bytes(data[pos : pos + 2], "little")
        pos += 2
    if len(data) != pos:
        raise ValueError("Glucose measurement has unexpected trailing bytes")
    tz = ZoneInfo(time_zone)
    local = wall.replace(tzinfo=tz)
    utc = local.astimezone(timezone.utc)
    if utc.astimezone(tz).replace(tzinfo=None) != wall:
        raise ValueError("Device time is nonexistent in the selected time zone")
    if local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
        raise ValueError("Device time is ambiguous in the selected time zone")
    return GlucoseReading(
        sequence,
        utc,
        value,
        unit,
        sample & 0x0F,
        sample >> 4,
        status,
        bool(flags & 0x10),
    )

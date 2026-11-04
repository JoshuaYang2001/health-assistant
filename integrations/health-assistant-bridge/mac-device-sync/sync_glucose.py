#!/usr/bin/env python3
"""Preview and, after confirmation, import an Accu-Chek meter's Bluetooth history."""

import argparse
import hashlib
import ipaddress
import json
import subprocess
import sys
import tempfile
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import requests
from glucose import decode_measurement

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python-sdk"))
from health_assistant_bridge import (
    ClientRecord,
    HealthAssistantBridgeClient,
    SyncPayload,
)


def check_server_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError(
            "Server address must contain only scheme, host and optional port"
        )
    if parsed.scheme == "https":
        return
    try:
        loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        loopback = parsed.hostname == "localhost"
    if parsed.scheme != "http" or not loopback:
        raise ValueError("Use HTTPS for any non-local server address")


def decode_transfer(transfer: dict, time_zone: str) -> list[ClientRecord]:
    device_id = str(UUID(transfer["device_id"]))
    packets = transfer["packets"]
    if not isinstance(packets, list) or len(packets) > 5000:
        raise ValueError("Invalid measurement transfer")
    records = []
    seen = {}
    for packet in packets:
        reading = decode_measurement(bytes.fromhex(packet), time_zone)
        if reading.sensor_status:
            raise ValueError(
                "The meter reported a sensor status warning. No readings were imported."
            )
        if reading.sample_type != 1:
            raise ValueError(
                "The meter returned a sample that is not capillary whole blood. No readings were imported."
            )
        if reading.context_follows:
            raise ValueError(
                "The meter returned extra reading context that is not yet supported. No readings were imported."
            )
        timestamp = reading.measured_at.isoformat()
        key = hashlib.sha256(
            f"{device_id}|{reading.sequence}|{timestamp}".encode()
        ).hexdigest()
        record = ClientRecord(
            external_id=key,
            type="quantitative",
            name="Glucose",
            code="15074-8" if reading.unit == "mmol/L" else "2339-0",
            coding_system="loinc",
            value=float(reading.value),
            unit=reading.unit,
            timestamp=timestamp,
            performer="Accu-Chek Instant",
        )
        if key in seen:
            if seen[key] != record:
                raise ValueError(
                    "The meter returned conflicting duplicate record identifiers"
                )
            continue
        seen[key] = record
        records.append(record)
    return sorted(records, key=lambda record: record.timestamp or "")


def read_meter(name_filter: str) -> dict:
    source = Path(__file__).with_name("GlucoseReader.swift")
    with tempfile.TemporaryDirectory(prefix="ha-glucose-") as directory:
        binary = Path(directory) / "glucose-reader"
        subprocess.run(
            ["swiftc", str(source), "-o", str(binary)], check=True, timeout=60
        )
        result = subprocess.run(
            [str(binary), name_filter], check=True, capture_output=True, timeout=120
        )
        return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview an Accu-Chek Instant transfer; --upload enables confirmed import."
    )
    parser.add_argument(
        "--timezone",
        required=True,
        help="IANA timezone of the meter clock, e.g. Asia/Shanghai",
    )
    parser.add_argument(
        "--name-filter",
        default="accu-chek",
        help="Case-insensitive Bluetooth device name substring",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Confirm and import readings through a signed Bridge connection",
    )
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8100",
        help="Health Assistant origin; HTTPS required except loopback",
    )
    parser.add_argument(
        "--bridge-id", help="Patient-scoped Bridge instance UUID; prompted if omitted"
    )
    args = parser.parse_args()
    try:
        if args.upload:
            raise ValueError("真实数据导入尚未完成实机验证，当前只支持预览")
        check_server_url(args.server)
        client = None
        if args.upload:
            bridge_id = str(
                UUID(args.bridge_id or input("Bridge instance ID: ").strip())
            )
            secret = getpass("Bridge API secret (input hidden): ")
            if not secret:
                raise ValueError("A Bridge API secret is required")
            client = HealthAssistantBridgeClient(
                args.server, bridge_id, api_secret=secret, max_retries=1
            )
            status = client.get_status()
            if "flat_record_idempotency" not in status.bridge_features:
                raise ValueError(
                    "Server does not advertise safe record deduplication; update and migrate it first"
                )
        print(
            "Scanning for the meter. Complete the macOS Bluetooth pairing prompt if shown.",
            file=sys.stderr,
            flush=True,
        )
        transfer = read_meter(args.name_filter)
        records = decode_transfer(transfer, args.timezone)
        print(
            f"Read {len(records)} measurements. Meter clock timezone: {args.timezone}."
        )
        for record in records:
            print(f"{record.timestamp}  {record.value:g} {record.unit}")
        if not records or not client:
            return 0
        choice = input(
            "Confirm the meter, patient and device clock are correct; import these readings? [y/N] "
        )
        if choice.strip().lower() != "y":
            print("Import cancelled.")
            return 0
        response = client.sync_data(
            SyncPayload(
                client_version="1.0", source_system="accu_chek_instant", records=records
            )
        )
        if not response.success:
            raise RuntimeError("Server reported an import failure")
        print(
            f"Import complete: {response.metrics_synced} new readings; existing readings were skipped."
        )
        return 0
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            print(exc.stderr.decode("utf-8", errors="replace").strip(), file=sys.stderr)
        else:
            print(
                "The macOS Bluetooth helper could not be built or run.", file=sys.stderr
            )
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        RuntimeError,
        subprocess.TimeoutExpired,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
    except requests.RequestException:
        print(
            "The bridge request failed. No successful import was confirmed; retry only after checking the server.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())

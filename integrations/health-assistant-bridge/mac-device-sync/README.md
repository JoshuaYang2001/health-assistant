# macOS device integration — work in progress

This directory contains an experimental, **read-only preview** of Accu-Chek Instant Bluetooth records and a read-only Respironics SD-card directory inspector. Neither device has been tested against the user's hardware. The glucose upload switch is deliberately disabled, and raw SD-card parsing and import have not been implemented. Do not treat this as a completed device integration.

## Accu-Chek Instant

Requirements: macOS with Bluetooth, Swift command-line tools, the project Python environment, and a meter in pairing mode. The meter can only pair with a limited number of devices; consult its manual before changing an existing pairing. macOS may ask for Bluetooth access and the meter's pairing PIN. Enter the PIN into the operating system prompt only; do not put it in a command, source code, logs, or version control.

From the repository root, after putting the meter in pairing mode:

```bash
.venv/bin/python integrations/health-assistant-bridge/mac-device-sync/sync_glucose.py --timezone Asia/Shanghai
```

The timezone must match the meter's clock. The preview prints health readings to the local terminal; it does not save or upload them. The helper compiles a temporary CoreBluetooth executable, scans for the device name `accu-chek`, requests stored records, and waits for a complete transfer. `--name-filter` can select a different advertised name. The result must be checked against the meter, including readings, timestamp, units and flags. Unsupported measurement context, invalid values, incomplete transfers and sensor status warnings fail closed.

The separate Bridge idempotency implementation has only been exercised using simulated data in the isolated test database. Actual patient import is **disabled** until real-device verification and review. The experimental `--upload` option intentionally stops before obtaining credentials or connecting to the device. It must not be enabled just by passing flags. Production use would also require applying the new database migration, configuring a patient-scoped Bridge, and verifying a secure phone-to-server connection.

## Respironics SD card

After inserting a card, select its actual mounted directory and run:

```bash
.venv/bin/python integrations/health-assistant-bridge/mac-device-sync/inspect_cpap_sd.py '/Volumes/your-card'
```

This inventories candidate `P-Series` directory names and file extensions without reading file contents or writing to the card. It does not determine whether a file is compatible or import records. Device-specific parsing must be built and validated after examining an actual 557P card and confirming the ownership and meaning of its data. Do not format or modify the original card.

## Verification

```bash
.venv/bin/pytest -q integrations/health-assistant-bridge/mac-device-sync/tests
cd backend
HA_ENV_FILE="$PWD/.env.test" ../.venv/bin/pytest -q tests/test_bridge_record_receipts.py tests/test_health_assistant_bridge.py tests/test_bridge_schema_published.py
```

The database tests require an isolated `_test` database and migrate/truncate its tables. They must never point at a live database. Tests use synthetic data only.

"""Exercise bridge record deduplication against the migrated test database."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.extensions.builtin.health_assistant_bridge.provider import (
    ClientRecord,
    HealthAssistantBridgeProvider,
    SyncPayload,
    _claim_flat_records,
)
from app.extensions.sdk.observation_builder import ObservationBuilder
from app.models.fhir.patient import Observation, Patient
from app.models.tenant_model import TenantModel
from app.models.user_integration import UserIntegration
from app.models.user_model import UserModel


@pytest.mark.asyncio
async def test_flat_record_import_is_atomic_and_idempotent():
    tenant_id, patient_id, user_id, integration_id = (uuid4() for _ in range(4))
    async with AsyncSessionLocal() as db:
        db.add(TenantModel(id=tenant_id, name="Test", slug=f"device-{tenant_id.hex}"))
        await db.flush()
        db.add(
            UserModel(
                id=user_id, email=f"{user_id}@example.test", tenant_id=tenant_id, role="ADMIN"
            )
        )
        db.add(
            Patient(id=patient_id, tenant_id=tenant_id, name={"family": "Test"}, gender="UNKNOWN")
        )
        await db.flush()
        db.add(
            UserIntegration(
                id=integration_id,
                tenant_id=tenant_id,
                patient_id=patient_id,
                user_id=user_id,
                provider="health_assistant_bridge",
                status="ACTIVE",
                user_config={},
            )
        )
        await db.commit()
    async with AsyncSessionLocal() as db:
        integration = (
            await db.execute(select(UserIntegration).where(UserIntegration.id == integration_id))
        ).scalar_one()
    record = ClientRecord(
        external_id="meter-record-1",
        type="quantitative",
        name="Glucose",
        code="15074-8",
        coding_system="loinc",
        value=5.5,
        unit="mmol/L",
        timestamp="2026-11-03T09:00:00+00:00",
    )
    payload = SyncPayload(
        client_version="test", source_system="accu_chek_instant", records=[record]
    )
    provider = HealthAssistantBridgeProvider()
    builder = ObservationBuilder(tenant_id, patient_id)
    assert await provider._process_and_save_sync_data(integration, payload, builder) == 1
    assert await provider._process_and_save_sync_data(integration, payload, builder) == 0
    changed = record.model_copy(update={"value": 6.5})
    with pytest.raises(ValueError, match="identifier was reused"):
        await provider._process_and_save_sync_data(
            integration, payload.model_copy(update={"records": [changed]}), builder
        )

    concurrent_payload = payload.model_copy(
        update={"records": [record.model_copy(update={"external_id": "concurrent"})]}
    )

    async def concurrent_sync():
        async with AsyncSessionLocal() as db:
            current = (
                await db.execute(
                    select(UserIntegration).where(UserIntegration.id == integration_id)
                )
            ).scalar_one()
        return await provider._process_and_save_sync_data(
            current, concurrent_payload, ObservationBuilder(tenant_id, patient_id)
        )

    assert sorted(await asyncio.gather(concurrent_sync(), concurrent_sync())) == [0, 1]
    async with AsyncSessionLocal() as db:
        count = (
            await db.execute(
                text("SELECT count(*) FROM bridge_record_receipts WHERE integration_id = :id"),
                {"id": integration_id},
            )
        ).scalar_one()
        assert count == 2
        observations = (
            (await db.execute(select(Observation).where(Observation.patient_id == patient_id)))
            .scalars()
            .all()
        )
        telemetry_count = (
            await db.execute(
                text(
                    "SELECT count(*) FROM telemetry_data "
                    "WHERE tenant_id = :tenant AND patient_id = :patient"
                ),
                {"tenant": tenant_id, "patient": patient_id},
            )
        ).scalar_one()
        assert len(observations) + telemetry_count == 2


@pytest.mark.asyncio
async def test_claim_rolls_back_with_transaction():
    tenant_id, patient_id, user_id, integration_id = (uuid4() for _ in range(4))
    async with AsyncSessionLocal() as db:
        db.add(TenantModel(id=tenant_id, name="Test", slug=f"device-{tenant_id.hex}"))
        await db.flush()
        db.add(
            UserModel(
                id=user_id, email=f"{user_id}@example.test", tenant_id=tenant_id, role="ADMIN"
            )
        )
        db.add(
            Patient(id=patient_id, tenant_id=tenant_id, name={"family": "Test"}, gender="UNKNOWN")
        )
        await db.flush()
        integration = UserIntegration(
            id=integration_id,
            tenant_id=tenant_id,
            patient_id=patient_id,
            user_id=user_id,
            provider="health_assistant_bridge",
            status="ACTIVE",
            user_config={},
        )
        db.add(integration)
        await db.commit()
        record = ClientRecord(
            external_id="rolled-back", type="quantitative", name="Glucose", value=5.0
        )
        assert len(await _claim_flat_records(db, integration, "device", [record])) == 1
        await db.rollback()
        await db.refresh(integration)
        assert len(await _claim_flat_records(db, integration, "device", [record])) == 1
        await db.rollback()

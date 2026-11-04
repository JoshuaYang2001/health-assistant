"""Add atomic idempotency keys for patient-scoped bridge observations.

Revision ID: e8d1c2a3b4f5
Revises: c1h2a4t5t6r
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e8d1c2a3b4f5"
down_revision = "c1h2a4t5t6r"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bridge_record_receipts",
        sa.Column(
            "integration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_integrations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fhir_patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_system", sa.String(128), primary_key=True),
        sa.Column("external_id", sa.String(128), primary_key=True),
        sa.Column("body_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade():
    op.drop_table("bridge_record_receipts")

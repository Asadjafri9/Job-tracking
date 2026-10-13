"""db003_quota_reservations

Revision ID: 45dd8a1bf301
Revises: 3b5a2c91d741
Create Date: 2026-10-13
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "45dd8a1bf301"
down_revision: Union[str, None] = "3b5a2c91d741"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quota_reservations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("reservation_key", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount BETWEEN 1 AND 52428800", name="ck_quota_reservations_quota_amount_bounds"),
        sa.CheckConstraint("length(kind) BETWEEN 1 AND 64", name="ck_quota_reservations_quota_kind_length"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_quota_reservations_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_quota_reservations"),
        sa.UniqueConstraint("user_id", "kind", "reservation_key", name="uq_quota_reservation_key"),
    )
    op.create_index(
        "ix_quota_reservations_expiry",
        "quota_reservations",
        ["user_id", "kind", "expires_at"],
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.quota_reservations TO copilot_runtime")
    op.execute("ALTER TABLE public.quota_reservations ENABLE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_isolation_quota_reservations ON public.quota_reservations
        FOR ALL TO copilot_runtime
        USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_quota_reservations ON public.quota_reservations")
    op.drop_table("quota_reservations")

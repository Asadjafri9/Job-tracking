"""m6_export_artifacts

Adds the private export artifact table for DATA-002 exports: one row per
export job, owner-scoped under RLS for copilot_runtime, with 24-hour expiry
tracked for the cleanup stage.

Revision ID: c6f2a9d84b17
Revises: 3b8e1f0a2c45
Create Date: 2026-10-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c6f2a9d84b17"
down_revision: str | None = "3b8e1f0a2c45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_artifacts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "BUILDING",
                "READY",
                "EXPIRED",
                "DELETED",
                name="export_artifact_state",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="BUILDING",
            nullable=False,
        ),
        sa.Column("redacted_error", sa.String(length=512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(sha256) = 64 OR sha256 IS NULL", name="export_sha_length"),
        sa.CheckConstraint("size_bytes >= 0", name="export_size_nonnegative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "id", name="uq_export_artifacts_user_id_id"),
        sa.UniqueConstraint("job_id", name="uq_export_artifacts_job"),
    )
    op.create_index(
        "ix_export_artifacts_user_created",
        "export_artifacts",
        ["user_id", "created_at"],
    )
    op.execute('REVOKE ALL PRIVILEGES ON TABLE public."export_artifacts" FROM PUBLIC')
    op.execute(
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public."export_artifacts" '
        "TO copilot_runtime"
    )
    op.execute('ALTER TABLE public."export_artifacts" ENABLE ROW LEVEL SECURITY')
    op.execute(
        '''CREATE POLICY "tenant_isolation_export_artifacts"
            ON public."export_artifacts"
            FOR ALL TO copilot_runtime
            USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
            WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)'''
    )
    # The independent deletion journal is content-free (hashes only): the
    # runtime role records the journal before acknowledging deletion and
    # reads its own hash for idempotency. Rows are never updated or
    # removed by the application.
    op.execute(
        'GRANT SELECT, INSERT ON TABLE public."deletion_journal" TO copilot_runtime'
    )
    # users is identity bootstrap owned by the auth role; blanket RLS would
    # break subject lookups before user_id is known. Instead the runtime
    # role reads exactly its own row through this view and scrubs it only
    # through the tombstone function during staged deletion.
    op.execute(
        """CREATE VIEW copilot_current_user AS
        SELECT id, issuer, subject, state, timezone, beta_eligible, created_at
        FROM public.users
        WHERE id = NULLIF(current_setting('app.user_id', true), '')::uuid"""
    )
    op.execute('GRANT SELECT ON copilot_current_user TO copilot_runtime')
    op.execute(
        """CREATE FUNCTION copilot_tombstone_user() RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE
            owner uuid := NULLIF(current_setting('app.user_id', true), '')::uuid;
        BEGIN
            IF owner IS NULL THEN
                RAISE EXCEPTION 'app.user_id is not set';
            END IF;
            UPDATE public.users
               SET state = 'DELETED',
                   login_email = 'deleted-' || id::text || '@tombstone.invalid',
                   login_email_verified = false
             WHERE id = owner AND state = 'DELETING';
        END; $$"""
    )
    op.execute('GRANT EXECUTE ON FUNCTION copilot_tombstone_user() TO copilot_runtime')
    op.execute(
        """CREATE FUNCTION copilot_begin_deletion() RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE
            owner uuid := NULLIF(current_setting('app.user_id', true), '')::uuid;
            changed integer;
        BEGIN
            IF owner IS NULL THEN
                RAISE EXCEPTION 'app.user_id is not set';
            END IF;
            UPDATE public.users SET state = 'DELETING'
             WHERE id = owner AND state = 'ACTIVE';
            GET DIAGNOSTICS changed = ROW_COUNT;
            RETURN changed > 0;
        END; $$"""
    )
    op.execute('GRANT EXECUTE ON FUNCTION copilot_begin_deletion() TO copilot_runtime')


def downgrade() -> None:
    # Dropping an object removes its privileges; REVOKE on an object that
    # was never created aborts transactional DDL, so drops come first.
    op.execute('DROP FUNCTION IF EXISTS copilot_begin_deletion()')
    op.execute('DROP FUNCTION IF EXISTS copilot_tombstone_user()')
    op.execute('DROP VIEW IF EXISTS copilot_current_user')
    op.execute('REVOKE SELECT, INSERT ON TABLE public."deletion_journal" FROM copilot_runtime')
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_export_artifacts" '
        'ON public."export_artifacts"'
    )
    op.drop_table("export_artifacts")

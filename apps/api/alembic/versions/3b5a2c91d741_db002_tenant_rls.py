"""db002_tenant_rls

Revision ID: 3b5a2c91d741
Revises: 0efe8de248fa
Create Date: 2026-10-13
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

revision: str = "3b5a2c91d741"
down_revision: Union[str, None] = "0efe8de248fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Owner-scoped v2 tables. Identity bootstrap tables and the independent
# deletion journal are deliberately outside this application's tenant role.
TENANT_TABLES = (
    "ai_attempts",
    "ai_operations",
    "application_answers",
    "application_sessions",
    "application_status_events",
    "applications",
    "audit_events",
    "discovered_jobs",
    "document_extractions",
    "documents",
    "email_draft_documents",
    "email_draft_events",
    "email_drafts",
    "extension_grants",
    "idempotency_records",
    "jobs",
    "monitored_sources",
    "monitoring_runs",
    "notifications",
    "profile_fact_versions",
    "profile_facts",
    "profiles",
    "provider_credentials",
    "provider_routes",
    "provider_settings",
    "sessions",
    "submission_events",
)


def upgrade() -> None:
    op.add_column(
        "auth_transactions",
        sa.Column("extension_pkce_challenge", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "auth_transactions",
        sa.Column("browser_binding_hash", sa.String(length=64), nullable=True),
    )
    op.execute("UPDATE public.auth_transactions SET browser_binding_hash = repeat('0', 64)")
    op.alter_column("auth_transactions", "browser_binding_hash", nullable=False)
    op.create_check_constraint(
        op.f("ck_auth_transactions_browser_binding_hash_length"),
        "auth_transactions",
        "length(browser_binding_hash) = 64",
    )
    op.add_column(
        "auth_transactions",
        sa.Column("extension_state", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "auth_transactions",
        sa.Column("require_fresh_auth", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "extension_grants",
        sa.Column(
            "state_hash", sa.String(length=64), nullable=False,
            server_default=sa.text("repeat('0', 64)"),
        ),
    )
    op.execute("UPDATE public.extension_grants SET revoked_at = now()")
    op.alter_column("extension_grants", "state_hash", server_default=None)
    op.create_check_constraint(
        op.f("ck_extension_grants_state_hash_length"), "extension_grants", "length(state_hash) = 64"
    )
    if not context.is_offline_mode():
        bind = op.get_bind()
        runtime_role = bind.execute(
            sa.text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :name"),
            {"name": "copilot_runtime"},
        ).one_or_none()
        if runtime_role is None:
            raise RuntimeError("copilot_runtime must exist before applying DB-002")
        if runtime_role.rolsuper or runtime_role.rolbypassrls:
            raise RuntimeError("copilot_runtime must not be superuser or bypass row security")
        auth_role = bind.execute(
            sa.text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :name"),
            {"name": "copilot_auth"},
        ).one_or_none()
        if auth_role is None or auth_role.rolsuper or auth_role.rolbypassrls:
            raise RuntimeError("copilot_auth must exist without superuser or BYPASSRLS")
        worker_role = bind.execute(
            sa.text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :name"),
            {"name": "copilot_worker"},
        ).one_or_none()
        if worker_role is None or worker_role.rolsuper or worker_role.rolbypassrls:
            raise RuntimeError("copilot_worker must exist without superuser or BYPASSRLS")

    op.execute("GRANT USAGE ON SCHEMA public TO copilot_runtime")
    op.execute("GRANT USAGE ON SCHEMA public TO copilot_auth")
    op.execute("GRANT USAGE ON SCHEMA public TO copilot_worker")
    op.execute("GRANT SELECT, INSERT ON TABLE public.users TO copilot_auth")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.auth_transactions TO copilot_auth"
    )
    for table in ("profiles",):
        op.execute(
            sa.text(
                f'GRANT SELECT, INSERT ON TABLE public."{table}" TO copilot_auth'
            )
        )
    for table in ("sessions", "extension_grants"):
        op.execute(
            sa.text(
                f'GRANT SELECT, INSERT, UPDATE ON TABLE public."{table}" TO copilot_auth'
            )
        )
    for table in TENANT_TABLES:
        op.execute(sa.text(f'REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM PUBLIC'))
        op.execute(
            sa.text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public."{table}" '
                "TO copilot_runtime"
            )
        )
        op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))
        policy_roles = (
            "copilot_runtime, copilot_auth"
            if table in {"sessions", "extension_grants", "profiles"}
            else "copilot_runtime"
        )
        op.execute(
            sa.text(
                f'''CREATE POLICY "tenant_isolation_{table}"
                    ON public."{table}"
                    FOR ALL TO {policy_roles}
                    USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
                    WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)'''
            )
        )
    op.execute(
        """CREATE POLICY auth_lookup_sessions ON public.sessions
        FOR SELECT TO copilot_auth
        USING (
            token_hash = NULLIF(current_setting('app.auth_session_hash', true), '')
            OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
        )"""
    )
    op.execute(
        """CREATE POLICY auth_write_sessions ON public.sessions
        FOR INSERT TO copilot_auth
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"""
    )
    op.execute(
        """CREATE POLICY auth_update_sessions ON public.sessions
        FOR UPDATE TO copilot_auth
        USING (
            token_hash = NULLIF(current_setting('app.auth_session_hash', true), '')
            OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
        )
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"""
    )
    op.execute(
        """CREATE POLICY auth_lookup_extension_grants ON public.extension_grants
        FOR SELECT TO copilot_auth
        USING (
            grant_hash = NULLIF(current_setting('app.auth_grant_hash', true), '')
            OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
        )"""
    )
    op.execute(
        """CREATE POLICY auth_write_extension_grants ON public.extension_grants
        FOR INSERT TO copilot_auth
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"""
    )
    op.execute(
        """CREATE POLICY auth_update_extension_grants ON public.extension_grants
        FOR UPDATE TO copilot_auth
        USING (
            grant_hash = NULLIF(current_setting('app.auth_grant_hash', true), '')
            OR user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
        )
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)"""
    )
    op.execute("GRANT SELECT, UPDATE ON TABLE public.jobs TO copilot_worker")
    op.execute(
        """CREATE POLICY worker_claim_jobs ON public.jobs
        FOR ALL TO copilot_worker USING (true) WITH CHECK (true)"""
    )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation_{table}" ON public."{table}"'))
        op.execute(sa.text(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM copilot_runtime'))
        op.execute(sa.text(f'REVOKE ALL PRIVILEGES ON TABLE public."{table}" FROM copilot_auth'))
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.users FROM copilot_auth")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.auth_transactions FROM copilot_auth")
    op.execute("DROP POLICY IF EXISTS worker_claim_jobs ON public.jobs")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.jobs FROM copilot_worker")
    for policy, table in (
        ("auth_lookup_sessions", "sessions"),
        ("auth_write_sessions", "sessions"),
        ("auth_update_sessions", "sessions"),
        ("auth_lookup_extension_grants", "extension_grants"),
        ("auth_write_extension_grants", "extension_grants"),
        ("auth_update_extension_grants", "extension_grants"),
    ):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON public."{table}"'))
    op.drop_column("auth_transactions", "extension_pkce_challenge")
    op.drop_column("auth_transactions", "extension_state")
    op.drop_column("auth_transactions", "require_fresh_auth")
    op.drop_constraint(
        op.f("ck_auth_transactions_browser_binding_hash_length"),
        "auth_transactions",
        type_="check",
    )
    op.drop_column("auth_transactions", "browser_binding_hash")
    op.drop_constraint(
        op.f("ck_extension_grants_state_hash_length"), "extension_grants", type_="check"
    )
    op.drop_column("extension_grants", "state_hash")

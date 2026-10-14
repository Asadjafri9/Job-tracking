"""job001_scheduler_dispatch

Adds the SKIPPED monitoring-run state, grants the least-privilege
copilot_scheduler role for daily dispatch ticks, and enforces one active
durable job per (owner, kind, reference) so duplicate scheduler replicas
cannot enqueue the same run twice.

Revision ID: f7c91a2b3d4e
Revises: 8a62d76fa114
Create Date: 2026-10-14
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

revision: str = "f7c91a2b3d4e"
down_revision: Union[str, None] = "8a62d76fa114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RUN_STATES = ("QUEUED", "RUNNING", "PARTIAL", "SUCCEEDED", "FAILED", "SKIPPED", "CANCELED")


def upgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        scheduler_role = bind.execute(
            sa.text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :name"),
            {"name": "copilot_scheduler"},
        ).one_or_none()
        if scheduler_role is None or scheduler_role.rolsuper or scheduler_role.rolbypassrls:
            raise RuntimeError("copilot_scheduler must exist without superuser or BYPASSRLS")

    op.execute(
        """
        DO $$
        DECLARE state_constraint text;
        BEGIN
            SELECT conname INTO state_constraint
            FROM pg_constraint
            WHERE conrelid = 'public.monitoring_runs'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%''QUEUED''%';
            IF state_constraint IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE public.monitoring_runs DROP CONSTRAINT %I', state_constraint
                );
            END IF;
        END $$;
        """
    )
    op.create_check_constraint(
        "ck_monitoring_runs_monitor_run_state",
        "monitoring_runs",
        "state IN (" + ", ".join(f"'{state}'" for state in RUN_STATES) + ")",
    )

    op.create_index(
        "uq_jobs_active_reference",
        "jobs",
        ["user_id", "kind", "reference_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('QUEUED','RUNNING') AND reference_id IS NOT NULL"),
    )

    op.execute("GRANT USAGE ON SCHEMA public TO copilot_scheduler")
    op.execute(
        "GRANT SELECT (id, user_id, state, schedule, timezone, next_run_at, revision, "
        "scheduled_check_consented_at, consent_revision) "
        "ON public.monitored_sources TO copilot_scheduler"
    )
    op.execute(
        "GRANT UPDATE (state, next_run_at, updated_at) "
        "ON public.monitored_sources TO copilot_scheduler"
    )
    op.execute("GRANT SELECT, INSERT ON TABLE public.monitoring_runs TO copilot_scheduler")
    op.execute("GRANT SELECT, INSERT ON TABLE public.jobs TO copilot_scheduler")
    op.execute(
        """CREATE POLICY scheduler_due_sources ON public.monitored_sources
        FOR SELECT TO copilot_scheduler
        USING (schedule = 'DAILY' AND state IN ('ACTIVE','PAUSED','ERROR'))"""
    )
    op.execute(
        """CREATE POLICY scheduler_update_sources ON public.monitored_sources
        FOR UPDATE TO copilot_scheduler
        USING (schedule = 'DAILY' AND state IN ('ACTIVE','PAUSED','ERROR'))
        WITH CHECK (state IN ('ACTIVE','PAUSED','ERROR','UNSUPPORTED'))"""
    )
    op.execute(
        """CREATE POLICY scheduler_read_runs ON public.monitoring_runs
        FOR SELECT TO copilot_scheduler USING (true)"""
    )
    op.execute(
        """CREATE POLICY scheduler_insert_runs ON public.monitoring_runs
        FOR INSERT TO copilot_scheduler WITH CHECK (run_kind = 'DAILY')"""
    )
    op.execute(
        """CREATE POLICY scheduler_read_jobs ON public.jobs
        FOR SELECT TO copilot_scheduler USING (true)"""
    )
    op.execute(
        """CREATE POLICY scheduler_enqueue_jobs ON public.jobs
        FOR INSERT TO copilot_scheduler WITH CHECK (state = 'QUEUED')"""
    )


def downgrade() -> None:
    for policy, table in (
        ("scheduler_enqueue_jobs", "jobs"),
        ("scheduler_read_jobs", "jobs"),
        ("scheduler_insert_runs", "monitoring_runs"),
        ("scheduler_read_runs", "monitoring_runs"),
        ("scheduler_update_sources", "monitored_sources"),
        ("scheduler_due_sources", "monitored_sources"),
    ):
        op.execute(f'DROP POLICY IF EXISTS "{policy}" ON public."{table}"')
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.jobs FROM copilot_scheduler")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.monitoring_runs FROM copilot_scheduler")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.monitored_sources FROM copilot_scheduler")
    op.execute("REVOKE USAGE ON SCHEMA public FROM copilot_scheduler")
    op.drop_index("uq_jobs_active_reference", table_name="jobs")
    op.execute(
        """
        DO $$
        DECLARE state_constraint text;
        BEGIN
            SELECT conname INTO state_constraint
            FROM pg_constraint
            WHERE conrelid = 'public.monitoring_runs'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%''QUEUED''%';
            IF state_constraint IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE public.monitoring_runs DROP CONSTRAINT %I', state_constraint
                );
            END IF;
        END $$;
        """
    )
    op.create_check_constraint(
        "ck_monitoring_runs_monitor_run_state",
        "monitoring_runs",
        "state IN ('QUEUED','RUNNING','PARTIAL','SUCCEEDED','FAILED','CANCELED')",
    )

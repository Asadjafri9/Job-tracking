"""m2_extraction_kinds

Extends the AI operation kind check with EXTRACTION so document candidate
extraction can be recorded as a durable AI operation, and adds the
SUPPORTING_DOCUMENT document type from the onboarding contract.

Revision ID: 3b8e1f0a2c45
Revises: f7c91a2b3d4e
Create Date: 2026-10-14
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "3b8e1f0a2c45"
down_revision: Union[str, None] = "f7c91a2b3d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OPERATION_KINDS = ("AUTOFILL", "EMAIL", "JOB_MATCH", "EXTRACTION", "CLASSIFY")
OLD_OPERATION_KINDS = ("AUTOFILL", "EMAIL", "JOB_MATCH")
DOCUMENT_TYPES = ("RESUME", "LINKEDIN_PDF", "COVER_LETTER", "SUPPORTING_DOCUMENT", "OTHER")
OLD_DOCUMENT_TYPES = ("RESUME", "LINKEDIN_PDF", "COVER_LETTER", "OTHER")


def _alter_varchar_length(table: str, column: str, values: tuple[str, ...]) -> None:
    op.alter_column(
        table,
        column,
        type_=sa.VARCHAR(length=max(map(len, values))),
        existing_type=sa.VARCHAR(),
        schema="public",
    )


def _swap_kind_constraint(table: str, column: str, name: str, values: tuple[str, ...]) -> None:
    canonical = f"ck_{table}_{name}"
    op.execute(
        sa.text(
            f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {canonical}"
        )
    )
    # Legacy runs may have created the constraint with a duplicated prefix.
    op.execute(
        sa.text(
            f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS "
            f"ck_{table}_{canonical}"
        )
    )
    op.create_check_constraint(
        name,
        table,
        f"{column} IN (" + ", ".join(f"'{value}'" for value in values) + ")",
    )


def upgrade() -> None:
    _swap_kind_constraint("ai_operations", "kind", "ai_operation_kind", OPERATION_KINDS)
    _swap_kind_constraint("documents", "document_type", "document_type", DOCUMENT_TYPES)
    _alter_varchar_length("ai_operations", "kind", OPERATION_KINDS)
    _alter_varchar_length("documents", "document_type", DOCUMENT_TYPES)


def downgrade() -> None:
    _alter_varchar_length("documents", "document_type", OLD_DOCUMENT_TYPES)
    _alter_varchar_length("ai_operations", "kind", OLD_OPERATION_KINDS)
    _swap_kind_constraint(
        "ai_operations", "kind", "ai_operation_kind", OLD_OPERATION_KINDS
    )
    _swap_kind_constraint(
        "documents", "document_type", "document_type", OLD_DOCUMENT_TYPES
    )

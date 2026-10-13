"""session_client_type

Revision ID: 8a62d76fa114
Revises: 45dd8a1bf301
Create Date: 2026-10-13
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8a62d76fa114"
down_revision: Union[str, None] = "45dd8a1bf301"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("client_type", sa.String(length=16), server_default="WEB", nullable=False),
    )
    op.create_check_constraint(
        "ck_sessions_client_type_valid", "sessions", "client_type IN ('WEB', 'EXTENSION')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_sessions_client_type_valid", "sessions", type_="check")
    op.drop_column("sessions", "client_type")

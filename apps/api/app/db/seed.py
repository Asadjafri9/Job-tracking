"""Idempotent local-only synthetic seed for schema verification and UI development."""

from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy import create_engine, func
from sqlalchemy.dialects.postgresql import insert

from app.db.connection import sqlalchemy_url
from app.db.models import Profile, ProfileFact, ProfileFactVersion, User

SEED_USER_ID = UUID("b48b1673-12f0-4ac2-a791-7432e8edc001")
SEED_DIRECTORY_ID = UUID("b48b1673-12f0-4ac2-a791-7432e8edc002")
SEED_PROFILE_ID = UUID("b48b1673-12f0-4ac2-a791-7432e8edc003")
SEED_FACT_ID = UUID("b48b1673-12f0-4ac2-a791-7432e8edc004")
SEED_FACT_VERSION_ID = UUID("b48b1673-12f0-4ac2-a791-7432e8edc005")
SEED_ISSUER = "urn:local:synthetic-db-seed"
SEED_SUBJECT = "synthetic-job-seeker-001"


def seed(connection) -> None:
    """Insert one fictional user/profile/fact; safe to call repeatedly."""
    connection.execute(
        insert(User)
        .values(
            id=SEED_USER_ID,
            issuer=SEED_ISSUER,
            subject=SEED_SUBJECT,
            directory_object_id=SEED_DIRECTORY_ID,
            login_email="synthetic.user@example.test",
            login_email_verified=True,
            state="ACTIVE",
            timezone="Asia/Karachi",
            beta_eligible=True,
        )
        .on_conflict_do_nothing(index_elements=[User.issuer, User.subject])
    )
    connection.execute(
        insert(Profile)
        .values(id=SEED_PROFILE_ID, user_id=SEED_USER_ID, current_revision=1)
        .on_conflict_do_nothing(index_elements=[Profile.user_id])
    )
    connection.execute(
        insert(ProfileFact)
        .values(
            id=SEED_FACT_ID,
            user_id=SEED_USER_ID,
            profile_id=SEED_PROFILE_ID,
            fact_key="preferred_role",
            value_type="TEXT",
            value="Product Designer",
            sensitivity="NORMAL",
            allowed_purposes=["AUTOFILL", "JOB_MATCH"],
            current_revision=1,
        )
        .on_conflict_do_nothing(
            index_elements=[ProfileFact.user_id, ProfileFact.profile_id, ProfileFact.fact_key]
        )
    )
    connection.execute(
        insert(ProfileFactVersion)
        .values(
            id=SEED_FACT_VERSION_ID,
            user_id=SEED_USER_ID,
            profile_fact_id=SEED_FACT_ID,
            revision=1,
            value="Product Designer",
            source_type="MANUAL",
            source_ref="synthetic seed input",
            source_anchor={},
            confirmation_state="CONFIRMED",
            confirmed_at=func.now(),
        )
        .on_conflict_do_nothing(
            index_elements=[
                ProfileFactVersion.user_id,
                ProfileFactVersion.profile_fact_id,
                ProfileFactVersion.revision,
            ]
        )
    )


def main() -> None:
    """Seed only loopback databases and require an explicit local opt-in."""
    if os.getenv("DB001_LOCAL_SEED") != "1":
        raise SystemExit("Refusing to seed: set DB001_LOCAL_SEED=1 for a local synthetic database")
    database_url = os.getenv("MIGRATION_DATABASE_URL")
    if not database_url:
        raise SystemExit("MIGRATION_DATABASE_URL is required")
    from urllib.parse import urlparse

    if urlparse(database_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Synthetic DB-001 seed is restricted to loopback databases")
    engine = create_engine(sqlalchemy_url(database_url), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            seed(connection)
        print("Synthetic seed applied: 1 user, 1 profile, 1 confirmed fact version.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

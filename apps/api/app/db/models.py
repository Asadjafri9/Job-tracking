"""Version 2 persistence entities.

This module defines schema and relationships only. Tenant enforcement and role
grants are applied by versioned migrations; write APIs and concurrency protocols
belong to later tasks.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from app.db.base import Base


def enum_type(name: str, *values: str) -> SAEnum:
    return SAEnum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=max(map(len, values)),
    )


UUID_TYPE = sa.Uuid(as_uuid=True)
INSTANT = sa.DateTime(timezone=True)
JSON = JSONB
ID_DEFAULT = sa.text("gen_random_uuid()")
NOW_DEFAULT = sa.func.now()
MAX_EXTRACTION_CANDIDATES = 200
MAX_EXTRACTION_JSON_BYTES = 1_048_576
MAX_SOURCE_ANCHORS = 200
MAX_SOURCE_ANCHOR_JSON_BYTES = 262_144
MAX_SELECTED_FACT_VERSIONS = 40
MAX_SELECTED_FACT_VERSIONS_JSON_BYTES = 65_536
MAX_SELECTED_DOCUMENT_VERSIONS = 10
MAX_SELECTED_DOCUMENT_VERSIONS_JSON_BYTES = 32_768


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        sa.UniqueConstraint("issuer", "subject", name="uq_users_issuer_subject"),
        sa.UniqueConstraint("directory_object_id", name="uq_users_directory_object"),
        sa.CheckConstraint("length(issuer) BETWEEN 1 AND 512", name="issuer_length"),
        sa.CheckConstraint("length(subject) BETWEEN 1 AND 255", name="subject_length"),
        sa.CheckConstraint("length(login_email) BETWEEN 3 AND 320", name="email_length"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    issuer: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    subject: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    directory_object_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    login_email: Mapped[str] = mapped_column(sa.String(320), nullable=False)
    login_email_verified: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    state: Mapped[str] = mapped_column(
        enum_type("user_state", "ACTIVE", "DELETING", "DELETED"),
        nullable=False,
        server_default="ACTIVE",
    )
    timezone: Mapped[str] = mapped_column(sa.String(64), nullable=False, server_default="UTC")
    beta_eligible: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT, onupdate=NOW_DEFAULT
    )

    profile: Mapped[Profile | None] = relationship(back_populates="user", uselist=False)


class AuthTransaction(Base):
    __tablename__ = "auth_transactions"
    __table_args__ = (
        sa.UniqueConstraint("state_hash", name="uq_auth_transactions_state_hash"),
        sa.CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        sa.CheckConstraint("length(state_hash) = 64", name="state_hash_length"),
        sa.CheckConstraint("length(nonce_hash) = 64", name="nonce_hash_length"),
        sa.CheckConstraint("length(browser_binding_hash) = 64", name="browser_binding_hash_length"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    state_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    nonce_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    browser_binding_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    verifier_ciphertext: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    callback_uri: Mapped[str] = mapped_column(sa.String(2048), nullable=False)
    client_id: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    extension_id: Mapped[str | None] = mapped_column(sa.String(128))
    extension_pkce_challenge: Mapped[str | None] = mapped_column(sa.String(128))
    extension_state: Mapped[str | None] = mapped_column(sa.String(128))
    require_fresh_auth: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    pkce_challenge: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(INSTANT)
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "id", name="uq_sessions_user_id_id"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
        sa.CheckConstraint("expires_at > auth_time", name="expiry_after_auth"),
        sa.CheckConstraint("last_seen_at >= auth_time", name="last_seen_after_auth"),
        sa.CheckConstraint("length(token_hash) = 64", name="token_hash_length"),
        sa.CheckConstraint("client_type IN ('WEB', 'EXTENSION')", name="client_type_valid"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    token_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    client_type: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="WEB")
    auth_time: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(INSTANT)
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )


class ExtensionGrant(Base):
    __tablename__ = "extension_grants"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id", "session_id"], ["sessions.user_id", "sessions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("grant_hash", name="uq_extension_grants_hash"),
        sa.CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
        sa.CheckConstraint("length(grant_hash) = 64", name="grant_hash_length"),
        sa.CheckConstraint("length(state_hash) = 64", name="state_hash_length"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    session_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    grant_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    client_id: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    extension_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    pkce_challenge: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    state_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    expires_at: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(INSTANT)
    revoked_at: Mapped[datetime | None] = mapped_column(INSTANT)


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_profiles_user_id"),
        sa.UniqueConstraint("user_id", "id", name="uq_profiles_user_id_id"),
        sa.CheckConstraint("current_revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    current_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT, onupdate=NOW_DEFAULT
    )

    user: Mapped[User] = relationship(back_populates="profile")
    facts: Mapped[list[ProfileFact]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "id", name="uq_documents_user_id_id"),
        sa.UniqueConstraint("user_id", "id", "revision", name="uq_documents_user_id_id_revision"),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint("size_bytes BETWEEN 1 AND 5242880", name="document_size_limit"),
        sa.CheckConstraint("length(file_name) BETWEEN 1 AND 255", name="filename_length"),
        sa.CheckConstraint("length(storage_key) BETWEEN 1 AND 1024", name="storage_key_length"),
        sa.CheckConstraint("length(sha256) = 64", name="sha256_length"),
        sa.Index(
            "uq_documents_current_default",
            "user_id",
            unique=True,
            postgresql_where=sa.text("is_default AND is_current"),
        ),
        sa.Index("ix_documents_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    document_type: Mapped[str] = mapped_column(
        enum_type(
            "document_type",
            "RESUME",
            "LINKEDIN_PDF",
            "COVER_LETTER",
            "SUPPORTING_DOCUMENT",
            "OTHER",
        ),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    storage_key: Mapped[str] = mapped_column(sa.String(1024), nullable=False)
    file_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(sa.String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    original_state: Mapped[str] = mapped_column(
        enum_type("document_original_state", "RESERVED", "READY", "FAILED", "DELETED"),
        nullable=False,
        server_default="RESERVED",
    )
    parse_state: Mapped[str] = mapped_column(
        enum_type("document_parse_state", "NOT_STARTED", "QUEUED", "RUNNING", "PARSED", "FAILED"),
        nullable=False,
        server_default="NOT_STARTED",
    )
    is_current: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    is_default: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    deleted_at: Mapped[datetime | None] = mapped_column(INSTANT)

    extractions: Mapped[list[DocumentExtraction]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ProfileFact(Base):
    __tablename__ = "profile_facts"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "profile_id"], ["profiles.user_id", "profiles.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_profile_facts_user_id_id"),
        sa.UniqueConstraint(
            "user_id", "profile_id", "fact_key", name="uq_profile_facts_profile_key"
        ),
        sa.CheckConstraint("current_revision >= 1", name="positive_revision"),
        sa.CheckConstraint("length(fact_key) BETWEEN 1 AND 128", name="fact_key_length"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    profile_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    fact_key: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    value_type: Mapped[str] = mapped_column(
        enum_type("profile_fact_value_type", "TEXT", "NUMBER", "DATE", "BOOLEAN", "URL", "JSON"),
        nullable=False,
    )
    value: Mapped[dict[str, Any] | list[Any] | str | int | float | bool | None] = mapped_column(
        JSON, nullable=False
    )
    sensitivity: Mapped[str] = mapped_column(
        enum_type("fact_sensitivity", "NORMAL", "SENSITIVE", "SPECIAL_CATEGORY"),
        nullable=False,
        server_default="NORMAL",
    )
    allowed_purposes: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    current_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT, onupdate=NOW_DEFAULT
    )

    profile: Mapped[Profile] = relationship(back_populates="facts")
    versions: Mapped[list[ProfileFactVersion]] = relationship(
        back_populates="fact", cascade="all, delete-orphan"
    )


class ProfileFactVersion(Base):
    __tablename__ = "profile_fact_versions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "profile_fact_id"],
            ["profile_facts.user_id", "profile_facts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "document_id", "document_revision"],
            ["documents.user_id", "documents.id", "documents.revision"],
            ondelete="SET NULL (document_id, document_revision)",
        ),
        sa.UniqueConstraint(
            "user_id", "profile_fact_id", "revision", name="uq_fact_versions_revision"
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_fact_versions_user_id_id"),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number BETWEEN 1 AND 10000", name="page_number_bounds"
        ),
        sa.CheckConstraint(
            "confirmation_state <> 'CONFIRMED' OR confirmed_at IS NOT NULL",
            name="confirmed_requires_timestamp",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    profile_fact_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    value: Mapped[dict[str, Any] | list[Any] | str | int | float | bool | None] = mapped_column(
        JSON, nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        enum_type("fact_source_type", "MANUAL", "DOCUMENT", "LINKEDIN", "PROJECT", "OTHER"),
        nullable=False,
    )
    source_ref: Mapped[str | None] = mapped_column(sa.String(1024))
    document_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    document_revision: Mapped[int | None] = mapped_column(sa.Integer)
    page_number: Mapped[int | None] = mapped_column(sa.Integer)
    source_anchor: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    confirmation_state: Mapped[str] = mapped_column(
        enum_type("fact_confirmation_state", "REVIEW_REQUIRED", "CONFIRMED", "REJECTED"),
        nullable=False,
        server_default="REVIEW_REQUIRED",
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(INSTANT)
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )

    fact: Mapped[ProfileFact] = relationship(back_populates="versions")


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "document_id", "document_revision"],
            ["documents.user_id", "documents.id", "documents.revision"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_document_extractions_user_id_id"),
        sa.UniqueConstraint(
            "user_id",
            "document_id",
            "document_revision",
            "parse_version",
            name="uq_document_extraction_parse",
        ),
        sa.CheckConstraint("document_revision >= 1", name="positive_document_revision"),
        sa.CheckConstraint(
            f"candidate_count BETWEEN 0 AND {MAX_EXTRACTION_CANDIDATES}",
            name="candidate_count_bounds",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(candidates) = 'array' "
            f"AND jsonb_array_length(candidates) <= {MAX_EXTRACTION_CANDIDATES} "
            "AND candidate_count = jsonb_array_length(candidates) "
            f"AND octet_length(candidates::text) <= {MAX_EXTRACTION_JSON_BYTES}",
            name="candidates_bounds",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_anchors) = 'array' "
            f"AND jsonb_array_length(source_anchors) <= {MAX_SOURCE_ANCHORS} "
            f"AND octet_length(source_anchors::text) <= {MAX_SOURCE_ANCHOR_JSON_BYTES}",
            name="source_anchors_bounds",
        ),
        sa.CheckConstraint(
            "extracted_text IS NULL OR octet_length(extracted_text) <= "
            f"{MAX_EXTRACTION_JSON_BYTES}",
            name="extracted_text_limit",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    document_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    document_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    parse_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(sa.String(64))
    model_version: Mapped[str | None] = mapped_column(sa.String(128))
    extracted_text: Mapped[str | None] = mapped_column(sa.Text)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    source_anchors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    candidate_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    review_state: Mapped[str] = mapped_column(
        enum_type("extraction_review_state", "QUEUED", "RUNNING", "REVIEW_REQUIRED", "FAILED"),
        nullable=False,
        server_default="QUEUED",
    )
    redacted_error: Mapped[str | None] = mapped_column(sa.String(512))
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )

    document: Mapped[Document] = relationship(back_populates="extractions")


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "id", name="uq_provider_credentials_user_id_id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_provider_credentials_provider"),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint("length(key_last4) = 4", name="last_four_length"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    provider: Mapped[str] = mapped_column(
        enum_type("provider_name", "OPENROUTER", "XAI", "GEMINI"), nullable=False
    )
    ciphertext: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    nonce: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    wrapped_dek: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    kek_version: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    key_last4: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    status: Mapped[str] = mapped_column(
        enum_type("provider_credential_status", "READY", "NEEDS_ATTENTION", "REVOKED"),
        nullable=False,
        server_default="READY",
    )
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    allow_interactive: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    allow_background: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT, onupdate=NOW_DEFAULT
    )
    revoked_at: Mapped[datetime | None] = mapped_column(INSTANT)


class ProviderSettings(Base):
    __tablename__ = "provider_settings"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_provider_settings_user"),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint(
            "interactive_consent_revision IS NULL OR interactive_consent_revision >= 1",
            name="interactive_consent_revision_positive",
        ),
        sa.CheckConstraint(
            "background_consent_revision IS NULL OR background_consent_revision >= 1",
            name="background_consent_revision_positive",
        ),
        sa.CheckConstraint(
            "fallback_consent_revision IS NULL OR fallback_consent_revision >= 1",
            name="fallback_consent_revision_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    interactive_consent_revision: Mapped[int | None] = mapped_column(sa.Integer)
    background_consent_revision: Mapped[int | None] = mapped_column(sa.Integer)
    fallback_consent_revision: Mapped[int | None] = mapped_column(sa.Integer)
    max_attempts: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, server_default="3")
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT, onupdate=NOW_DEFAULT
    )


class ProviderRoute(Base):
    """One ordered provider/model route tied to an owner's saved credential."""

    __tablename__ = "provider_routes"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["provider_settings.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id", "credential_id"],
            ["provider_credentials.user_id", "provider_credentials.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "credential_id", name="uq_provider_routes_credential"),
        sa.UniqueConstraint("user_id", "position", name="uq_provider_routes_position"),
        sa.CheckConstraint("position BETWEEN 1 AND 3", name="position_bounds"),
        sa.CheckConstraint("length(model_id) BETWEEN 1 AND 128", name="model_id_length"),
        sa.CheckConstraint(
            "interactive_enabled OR background_enabled", name="route_has_allowed_purpose"
        ),
        sa.Index("ix_provider_routes_user_enabled_order", "user_id", "enabled", "position"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    credential_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    position: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    model_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    interactive_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    background_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )


class AiOperation(Base):
    __tablename__ = "ai_operations"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "id", name="uq_ai_operations_user_id_id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_ai_operations_idempotency"),
        sa.CheckConstraint("length(input_hmac) = 64", name="input_hmac_length"),
        sa.CheckConstraint(
            "profile_revision IS NULL OR profile_revision >= 1", name="profile_revision_positive"
        ),
        sa.CheckConstraint(
            "context_revision IS NULL OR context_revision >= 1", name="context_revision_positive"
        ),
        sa.Index("ix_ai_operations_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    kind: Mapped[str] = mapped_column(
        enum_type(
            "ai_operation_kind", "AUTOFILL", "EMAIL", "JOB_MATCH", "EXTRACTION", "CLASSIFY"
        ),
        nullable=False,
    )
    input_hmac: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    profile_revision: Mapped[int | None] = mapped_column(sa.Integer)
    context_revision: Mapped[int | None] = mapped_column(sa.Integer)
    state: Mapped[str] = mapped_column(
        enum_type("ai_operation_state", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "UNKNOWN"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    completed_at: Mapped[datetime | None] = mapped_column(INSTANT)
    expires_at: Mapped[datetime | None] = mapped_column(INSTANT)

    attempts: Mapped[list[AiAttempt]] = relationship(
        back_populates="operation", cascade="all, delete-orphan"
    )


class AiAttempt(Base):
    __tablename__ = "ai_attempts"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "operation_id"],
            ["ai_operations.user_id", "ai_operations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "credential_id"],
            ["provider_credentials.user_id", "provider_credentials.id"],
            ondelete="SET NULL (credential_id)",
        ),
        sa.UniqueConstraint(
            "user_id", "operation_id", "attempt_number", name="uq_ai_attempt_number"
        ),
        sa.CheckConstraint("attempt_number BETWEEN 1 AND 3", name="attempt_number_bounds"),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0", name="input_tokens_nonnegative"
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0", name="output_tokens_nonnegative"
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    operation_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    attempt_number: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    credential_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    provider: Mapped[str] = mapped_column(
        enum_type("ai_attempt_provider", "OPENROUTER", "XAI", "GEMINI"), nullable=False
    )
    model: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    state: Mapped[str] = mapped_column(
        enum_type("ai_attempt_state", "DISPATCHED", "SUCCEEDED", "FAILED", "UNKNOWN"),
        nullable=False,
    )
    input_tokens: Mapped[int | None] = mapped_column(sa.Integer)
    output_tokens: Mapped[int | None] = mapped_column(sa.Integer)
    redacted_outcome: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    redacted_error: Mapped[str | None] = mapped_column(sa.String(512))
    dispatched_at: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(INSTANT)

    operation: Mapped[AiOperation] = relationship(back_populates="attempts")


class ApplicationSession(Base):
    __tablename__ = "application_sessions"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "id", name="uq_application_sessions_user_id_id"),
        sa.CheckConstraint("profile_revision >= 1", name="profile_revision_positive"),
        sa.CheckConstraint("context_revision >= 1", name="context_revision_positive"),
        sa.CheckConstraint("octet_length(job_context::text) <= 262144", name="job_context_limit"),
        sa.CheckConstraint(
            "jsonb_typeof(selected_fact_versions) = 'array' "
            f"AND jsonb_array_length(selected_fact_versions) <= {MAX_SELECTED_FACT_VERSIONS} "
            "AND octet_length(selected_fact_versions::text) <= "
            f"{MAX_SELECTED_FACT_VERSIONS_JSON_BYTES}",
            name="selected_fact_versions_bounds",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(selected_document_versions) = 'array' "
            "AND jsonb_array_length(selected_document_versions) <= "
            f"{MAX_SELECTED_DOCUMENT_VERSIONS} "
            "AND octet_length(selected_document_versions::text) <= "
            f"{MAX_SELECTED_DOCUMENT_VERSIONS_JSON_BYTES}",
            name="selected_document_versions_bounds",
        ),
        sa.Index("ix_application_sessions_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    employer: Mapped[str | None] = mapped_column(sa.String(255))
    role: Mapped[str | None] = mapped_column(sa.String(255))
    raw_job_url: Mapped[str | None] = mapped_column(sa.String(2048))
    canonical_job_url: Mapped[str | None] = mapped_column(sa.String(2048))
    job_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    selected_fact_versions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    selected_document_versions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    form_reference: Mapped[str | None] = mapped_column(sa.String(512))
    profile_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    context_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        enum_type(
            "application_session_state",
            "PREPARED",
            "ANALYZING",
            "READY_TO_REVIEW",
            "ABANDONED",
            "SUBMISSION_ATTEMPTED",
        ),
        nullable=False,
        server_default="PREPARED",
    )
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    expires_at: Mapped[datetime | None] = mapped_column(INSTANT)


class EmailDraft(Base):
    __tablename__ = "email_drafts"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "id", name="uq_email_drafts_user_id_id"),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint(
            "length(recipient_email) BETWEEN 3 AND 320", name="recipient_email_length"
        ),
        sa.CheckConstraint("octet_length(subject) <= 998", name="subject_limit"),
        sa.CheckConstraint("octet_length(body) <= 32768", name="body_limit"),
        sa.CheckConstraint(
            "job_description IS NULL OR octet_length(job_description) <= 131072",
            name="job_description_limit",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_fact_versions) = 'array' "
            f"AND jsonb_array_length(source_fact_versions) <= {MAX_SELECTED_FACT_VERSIONS} "
            "AND octet_length(source_fact_versions::text) <= "
            f"{MAX_SELECTED_FACT_VERSIONS_JSON_BYTES}",
            name="source_fact_versions_bounds",
        ),
        sa.Index("ix_email_drafts_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    recipient_email: Mapped[str] = mapped_column(sa.String(320), nullable=False)
    employer: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    job_description: Mapped[str | None] = mapped_column(sa.Text)
    subject: Mapped[str] = mapped_column(sa.String(998), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_fact_versions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    state: Mapped[str] = mapped_column(
        enum_type(
            "email_draft_state",
            "DRAFT",
            "READY_FOR_REVIEW",
            "COMPOSE_OPENED",
            "USER_CONFIRMED_SENT",
            "CANCELED",
        ),
        nullable=False,
        server_default="DRAFT",
    )
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT, onupdate=NOW_DEFAULT
    )
    selected_documents: Mapped[list[EmailDraftDocument]] = relationship(
        back_populates="email_draft", cascade="all, delete-orphan"
    )


class EmailDraftDocument(Base):
    """Live document selection for a draft; deleting a document unlinks it."""

    __tablename__ = "email_draft_documents"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "email_draft_id"],
            ["email_drafts.user_id", "email_drafts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "document_id", "document_revision"],
            ["documents.user_id", "documents.id", "documents.revision"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id",
            "email_draft_id",
            "document_id",
            "document_revision",
            name="uq_email_draft_documents_selection",
        ),
        sa.UniqueConstraint(
            "user_id", "email_draft_id", "position", name="uq_email_draft_documents_position"
        ),
        sa.CheckConstraint("position BETWEEN 1 AND 10", name="position_bounds"),
        sa.CheckConstraint("document_revision >= 1", name="positive_document_revision"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    email_draft_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    document_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    document_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    position: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)

    email_draft: Mapped[EmailDraft] = relationship(back_populates="selected_documents")
    document: Mapped[Document] = relationship(viewonly=True)


class EmailDraftEvent(Base):
    """Idempotent, content-bounded evidence of opening compose or user-confirmed send."""

    __tablename__ = "email_draft_events"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "email_draft_id"],
            ["email_drafts.user_id", "email_drafts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "application_id"],
            ["applications.user_id", "applications.id"],
            ondelete="SET NULL (application_id)",
        ),
        sa.UniqueConstraint(
            "user_id", "event_idempotency_key", name="uq_email_draft_event_idempotency"
        ),
        sa.CheckConstraint("draft_revision >= 1", name="positive_draft_revision"),
        sa.CheckConstraint("octet_length(evidence::text) <= 8192", name="evidence_size_limit"),
        sa.Index("ix_email_draft_events_history", "user_id", "email_draft_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    email_draft_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    application_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    event_idempotency_key: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    event_type: Mapped[str] = mapped_column(
        enum_type("email_draft_event_type", "COMPOSE_OPENED", "USER_CONFIRMED_SENT"),
        nullable=False,
    )
    draft_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id", "application_session_id"],
            ["application_sessions.user_id", "application_sessions.id"],
            ondelete="SET NULL (application_session_id)",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "email_draft_id"],
            ["email_drafts.user_id", "email_drafts.id"],
            ondelete="SET NULL (email_draft_id)",
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_applications_user_id_id"),
        sa.CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint(
            "(channel = 'WEB_FORM' AND email_draft_id IS NULL) OR "
            "(channel = 'EMAIL' AND application_session_id IS NULL) OR "
            "(channel = 'MANUAL' AND application_session_id IS NULL "
            "AND email_draft_id IS NULL)",
            name="channel_reference_consistency",
        ),
        sa.CheckConstraint(
            "status <> 'APPLIED' OR applied_at IS NOT NULL", name="applied_requires_evidence_time"
        ),
        sa.Index(
            "uq_applications_user_job_attempt",
            "user_id",
            "canonical_job_url",
            "attempt_number",
            unique=True,
            postgresql_where=sa.text("canonical_job_url IS NOT NULL"),
        ),
        sa.Index(
            "uq_applications_web_session",
            "user_id",
            "application_session_id",
            unique=True,
            postgresql_where=sa.text("application_session_id IS NOT NULL"),
        ),
        sa.Index(
            "uq_applications_email_draft",
            "user_id",
            "email_draft_id",
            unique=True,
            postgresql_where=sa.text("email_draft_id IS NOT NULL"),
        ),
        sa.Index("ix_applications_user_status_followup", "user_id", "status", "follow_up_date"),
        sa.Index("ix_applications_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    channel: Mapped[str] = mapped_column(
        enum_type("application_channel", "WEB_FORM", "EMAIL", "MANUAL"), nullable=False
    )
    employer: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    raw_job_url: Mapped[str | None] = mapped_column(sa.String(2048))
    canonical_job_url: Mapped[str | None] = mapped_column(sa.String(2048))
    attempt_number: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(
        enum_type(
            "application_status", "SUBMISSION_ATTEMPTED", "APPLIED", "NEEDS_FOLLOW_UP", "CLOSED"
        ),
        nullable=False,
        server_default="SUBMISSION_ATTEMPTED",
    )
    attempt_at: Mapped[datetime | None] = mapped_column(INSTANT)
    applied_at: Mapped[datetime | None] = mapped_column(INSTANT)
    applied_date: Mapped[date | None] = mapped_column(sa.Date)
    follow_up_date: Mapped[date | None] = mapped_column(sa.Date)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    application_session_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    email_draft_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    document_metadata_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT, onupdate=NOW_DEFAULT
    )


class SubmissionEvent(Base):
    __tablename__ = "submission_events"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "application_session_id"],
            ["application_sessions.user_id", "application_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "application_id"],
            ["applications.user_id", "applications.id"],
            ondelete="SET NULL (application_id)",
        ),
        sa.UniqueConstraint(
            "user_id", "event_idempotency_key", name="uq_submission_event_idempotency"
        ),
        sa.CheckConstraint("length(gesture_ref_hash) = 64", name="gesture_hash_length"),
        sa.CheckConstraint("octet_length(evidence::text) <= 32768", name="evidence_size_limit"),
        sa.Index(
            "ix_submission_events_application_time", "user_id", "application_id", "observed_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    application_session_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    application_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    event_idempotency_key: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    evidence_type: Mapped[str] = mapped_column(
        enum_type(
            "submission_evidence_type",
            "SUBMIT_CLICK",
            "VALIDATION_BLOCKED",
            "SITE_SIGNAL",
            "UNKNOWN",
        ),
        nullable=False,
    )
    evidence_source: Mapped[str] = mapped_column(
        enum_type(
            "submission_evidence_source", "USER_GESTURE", "CONTENT_OBSERVER", "USER_CONFIRMATION"
        ),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    gesture_ref_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    signal_code: Mapped[str | None] = mapped_column(sa.String(128))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")


class ApplicationStatusEvent(Base):
    __tablename__ = "application_status_events"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "application_id"],
            ["applications.user_id", "applications.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_application_status_events_user_id_id"),
        sa.Index(
            "ix_application_status_events_history", "user_id", "application_id", "occurred_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    application_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    old_status: Mapped[str | None] = mapped_column(
        enum_type(
            "application_old_status", "SUBMISSION_ATTEMPTED", "APPLIED", "NEEDS_FOLLOW_UP", "CLOSED"
        )
    )
    new_status: Mapped[str] = mapped_column(
        enum_type(
            "application_new_status", "SUBMISSION_ATTEMPTED", "APPLIED", "NEEDS_FOLLOW_UP", "CLOSED"
        ),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        enum_type("application_status_source", "SITE_EVIDENCE", "USER_CONFIRMATION", "SYSTEM"),
        nullable=False,
    )
    evidence_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )


class ApplicationAnswer(Base):
    __tablename__ = "application_answers"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "application_id"],
            ["applications.user_id", "applications.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint("length(field_key) BETWEEN 1 AND 255", name="field_key_length"),
        sa.Index("ix_application_answers_snapshot", "user_id", "application_id", "revision"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    application_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    field_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    answer_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    source_fact_version_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    provenance_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, server_default="{}"
    )
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )


class MonitoredSource(Base):
    __tablename__ = "monitored_sources"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "id", name="uq_monitored_sources_user_id_id"),
        sa.CheckConstraint("revision >= 1", name="positive_revision"),
        sa.CheckConstraint(
            "scheduled_check_consented_at IS NULL OR schedule = 'DAILY'",
            name="scheduled_consent_schedule",
        ),
        sa.CheckConstraint(
            "saved_key_consented_at IS NULL OR scheduled_check_consented_at IS NOT NULL",
            name="key_consent_requires_schedule_consent",
        ),
        sa.CheckConstraint(
            "state <> 'ACTIVE' OR schedule <> 'DAILY' OR "
            "(scheduled_check_consented_at IS NOT NULL AND consent_revision IS NOT NULL "
            "AND next_run_at IS NOT NULL)",
            name="active_daily_requires_scheduled_consent",
        ),
        sa.CheckConstraint(
            "next_run_at IS NULL OR "
            "(state = 'ACTIVE' AND schedule = 'DAILY' "
            "AND scheduled_check_consented_at IS NOT NULL AND consent_revision IS NOT NULL)",
            name="due_source_requires_scheduled_consent",
        ),
        sa.CheckConstraint("length(public_url) BETWEEN 8 AND 2048", name="public_url_length"),
        sa.Index("ix_monitored_sources_user_state", "user_id", "state"),
        sa.Index("ix_monitored_sources_schedule", "state", "next_run_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    public_url: Mapped[str] = mapped_column(sa.String(2048), nullable=False)
    source_kind: Mapped[str] = mapped_column(
        enum_type("monitor_source_kind", "HTML", "RSS", "ATS"), nullable=False
    )
    state: Mapped[str] = mapped_column(
        enum_type("monitor_source_state", "ACTIVE", "PAUSED", "UNSUPPORTED", "ERROR", "DELETED"),
        nullable=False,
        server_default="PAUSED",
    )
    region_selector: Mapped[str | None] = mapped_column(sa.String(128))
    schedule: Mapped[str] = mapped_column(
        enum_type("monitor_schedule", "DAILY", "MANUAL"), nullable=False, server_default="DAILY"
    )
    timezone: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    next_run_at: Mapped[datetime | None] = mapped_column(INSTANT)
    last_success_at: Mapped[datetime | None] = mapped_column(INSTANT)
    scheduled_check_consented_at: Mapped[datetime | None] = mapped_column(INSTANT)
    saved_key_consented_at: Mapped[datetime | None] = mapped_column(INSTANT)
    consent_revision: Mapped[int | None] = mapped_column(sa.Integer)
    last_etag: Mapped[str | None] = mapped_column(sa.String(512))
    last_content_hash: Mapped[str | None] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT, onupdate=NOW_DEFAULT
    )

    runs: Mapped[list[MonitoringRun]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class MonitoringRun(Base):
    __tablename__ = "monitoring_runs"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "source_id"],
            ["monitored_sources.user_id", "monitored_sources.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_monitoring_runs_user_id_id"),
        sa.CheckConstraint(
            "(run_kind = 'DAILY' AND scheduled_local_date IS NOT NULL) OR "
            "(run_kind = 'MANUAL' AND request_id IS NOT NULL)",
            name="run_kind_identity",
        ),
        sa.CheckConstraint(
            "completed_count >= 0 AND discovered_count >= 0", name="counts_nonnegative"
        ),
        sa.Index(
            "uq_monitoring_runs_daily_source_date",
            "user_id",
            "source_id",
            "scheduled_local_date",
            unique=True,
            postgresql_where=sa.text("run_kind = 'DAILY'"),
        ),
        sa.Index(
            "uq_monitoring_runs_manual_request",
            "user_id",
            "request_id",
            unique=True,
            postgresql_where=sa.text("run_kind = 'MANUAL'"),
        ),
        sa.Index("ix_monitoring_runs_user_started", "user_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    source_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    request_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    schedule_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    run_kind: Mapped[str] = mapped_column(
        enum_type("monitor_run_kind", "DAILY", "MANUAL"), nullable=False
    )
    scheduled_local_date: Mapped[date | None] = mapped_column(sa.Date)
    state: Mapped[str] = mapped_column(
        enum_type(
            "monitor_run_state",
            "QUEUED",
            "RUNNING",
            "PARTIAL",
            "SUCCEEDED",
            "FAILED",
            "SKIPPED",
            "CANCELED",
        ),
        nullable=False,
    )
    completeness: Mapped[str] = mapped_column(
        enum_type("monitor_run_completeness", "COMPLETE", "PARTIAL", "UNKNOWN"),
        nullable=False,
        server_default="UNKNOWN",
    )
    completed_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    discovered_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(INSTANT)
    ended_at: Mapped[datetime | None] = mapped_column(INSTANT)
    redacted_error: Mapped[str | None] = mapped_column(sa.String(512))
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )

    source: Mapped[MonitoredSource] = relationship(back_populates="runs")


class DiscoveredJob(Base):
    __tablename__ = "discovered_jobs"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["user_id", "source_id"],
            ["monitored_sources.user_id", "monitored_sources.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_discovered_jobs_user_id_id"),
        sa.CheckConstraint(
            "native_id IS NOT NULL OR canonical_job_url IS NOT NULL", name="job_identity_required"
        ),
        sa.CheckConstraint(
            "native_id IS NULL OR "
            "(native_id_namespace IS NOT NULL AND length(native_id_namespace) BETWEEN 1 AND 128)",
            name="native_identity_requires_namespace",
        ),
        sa.CheckConstraint("meaningful_revision >= 1", name="positive_meaningful_revision"),
        sa.CheckConstraint(
            "octet_length(evidence_anchors::text) <= 32768", name="evidence_size_limit"
        ),
        sa.Index(
            "uq_discovered_jobs_native_identity",
            "user_id",
            "source_id",
            "native_id_namespace",
            "native_id",
            unique=True,
            postgresql_where=sa.text("native_id IS NOT NULL"),
        ),
        sa.Index(
            "uq_discovered_jobs_url_identity",
            "user_id",
            "source_id",
            "canonical_job_url",
            unique=True,
            postgresql_where=sa.text("canonical_job_url IS NOT NULL"),
        ),
        sa.Index("ix_discovered_jobs_user_first_seen", "user_id", "first_seen_at"),
        sa.Index("ix_discovered_jobs_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    source_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    native_id_namespace: Mapped[str | None] = mapped_column(sa.String(128))
    native_id: Mapped[str | None] = mapped_column(sa.String(255))
    canonical_job_url: Mapped[str | None] = mapped_column(sa.String(2048))
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    employer: Mapped[str | None] = mapped_column(sa.String(255))
    location: Mapped[str | None] = mapped_column(sa.String(255))
    is_remote: Mapped[bool | None] = mapped_column(sa.Boolean)
    evidence_anchors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    meaningful_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    match_reason: Mapped[str | None] = mapped_column(sa.String(512))
    status: Mapped[str] = mapped_column(
        enum_type("discovered_job_status", "NEW", "SAVED", "DISMISSED", "CLOSED"),
        nullable=False,
        server_default="NEW",
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["user_id", "discovered_job_id"],
            ["discovered_jobs.user_id", "discovered_jobs.id"],
            ondelete="SET NULL (discovered_job_id)",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "monitoring_run_id"],
            ["monitoring_runs.user_id", "monitoring_runs.id"],
            ondelete="SET NULL (monitoring_run_id)",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "application_id"],
            ["applications.user_id", "applications.id"],
            ondelete="SET NULL (application_id)",
        ),
        sa.UniqueConstraint("user_id", "event_key", name="uq_notifications_event_key"),
        sa.CheckConstraint("length(event_key) BETWEEN 1 AND 255", name="event_key_length"),
        sa.CheckConstraint("octet_length(content) <= 2048", name="content_length"),
        sa.Index("ix_notifications_unread_time", "user_id", "read_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    discovered_job_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    monitoring_run_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    application_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    event_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    kind: Mapped[str] = mapped_column(
        enum_type(
            "notification_kind", "JOB_MATCH", "SOURCE_STATUS", "APPLICATION_STATUS", "SYSTEM"
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(INSTANT)
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "id", name="uq_jobs_user_id_id"),
        sa.CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        sa.CheckConstraint(
            "lease_until IS NULL OR lease_owner IS NOT NULL", name="lease_owner_required"
        ),
        sa.CheckConstraint(
            "encrypted_cleanup_payload IS NULL OR octet_length(encrypted_cleanup_payload) <= 65536",
            name="cleanup_payload_limit",
        ),
        sa.Index("ix_jobs_claim", "state", "next_run_at", "created_at"),
        sa.Index("ix_jobs_user_state", "user_id", "state", "created_at"),
        sa.Index("ix_jobs_lease", "state", "lease_until"),
        sa.Index(
            "uq_jobs_active_reference",
            "user_id",
            "kind",
            "reference_id",
            unique=True,
            postgresql_where=sa.text("state IN ('QUEUED','RUNNING') AND reference_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    kind: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(sa.String(64))
    reference_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    state: Mapped[str] = mapped_column(
        enum_type("job_state", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELED"),
        nullable=False,
        server_default="QUEUED",
    )
    stage: Mapped[str | None] = mapped_column(sa.String(64))
    lease_owner: Mapped[str | None] = mapped_column(sa.String(128))
    lease_until: Mapped[datetime | None] = mapped_column(INSTANT)
    heartbeat_at: Mapped[datetime | None] = mapped_column(INSTANT)
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    next_run_at: Mapped[datetime | None] = mapped_column(INSTANT)
    expires_at: Mapped[datetime | None] = mapped_column(INSTANT)
    result_storage_key: Mapped[str | None] = mapped_column(sa.String(1024))
    receipt_digest: Mapped[str | None] = mapped_column(sa.String(64))
    encrypted_cleanup_payload: Mapped[bytes | None] = mapped_column(BYTEA)
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT, onupdate=NOW_DEFAULT
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id", "route_key", "idempotency_key", name="uq_idempotency_scope_key"
        ),
        sa.CheckConstraint("length(route_key) BETWEEN 1 AND 255", name="route_key_length"),
        sa.CheckConstraint("length(input_hmac) = 64", name="input_hmac_length"),
        sa.CheckConstraint("response_status BETWEEN 100 AND 599", name="response_status_bounds"),
        sa.Index("ix_idempotency_expiry", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    route_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    input_hmac: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(sa.String(64))
    entity_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    response_status: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )


class QuotaReservation(Base):
    """Temporary capacity held atomically while a bounded operation completes."""

    __tablename__ = "quota_reservations"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "kind", "reservation_key", name="uq_quota_reservation_key"),
        sa.CheckConstraint("amount BETWEEN 1 AND 52428800", name="quota_amount_bounds"),
        sa.CheckConstraint("length(kind) BETWEEN 1 AND 64", name="quota_kind_length"),
        sa.Index("ix_quota_reservations_expiry", "user_id", "kind", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    kind: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    reservation_key: Mapped[UUID] = mapped_column(UUID_TYPE, nullable=False)
    amount: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(INSTANT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("length(actor_hash) = 64", name="actor_hash_length"),
        sa.CheckConstraint("octet_length(metadata::text) <= 8192", name="metadata_limit"),
        sa.Index("ix_audit_events_user_time", "user_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id: Mapped[UUID | None] = mapped_column(UUID_TYPE)
    actor_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(sa.String(64))
    entity_ref_hash: Mapped[str | None] = mapped_column(sa.String(64))
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, server_default="{}"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )


class DeletionJournal(Base):
    __tablename__ = "deletion_journal"
    __table_args__ = (
        sa.UniqueConstraint("user_id_hash", name="uq_deletion_journal_user_hash"),
        sa.CheckConstraint("length(user_id_hash) = 64", name="user_hash_length"),
        sa.CheckConstraint("length(integrity_hmac) = 64", name="integrity_hmac_length"),
        sa.CheckConstraint(
            "octet_length(revoked_credential_versions::text) <= 8192",
            name="revoked_versions_limit",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, server_default=ID_DEFAULT)
    user_id_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    revoked_credential_versions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    revoked_session_digest: Mapped[str | None] = mapped_column(sa.String(64))
    integrity_hmac: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(
        INSTANT, nullable=False, server_default=NOW_DEFAULT
    )

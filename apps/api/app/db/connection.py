"""PostgreSQL URL normalization for SQLAlchemy's locked psycopg 3 driver."""

from sqlalchemy.engine import URL, make_url


def sqlalchemy_url(value: str) -> URL:
    """Convert a psycopg-compatible PostgreSQL URL into the SQLAlchemy driver URL."""
    url = make_url(value)
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg")
    if url.drivername not in {"postgresql+psycopg", "postgresql+psycopg_async"}:
        raise ValueError("Database URL must select the PostgreSQL psycopg driver")
    return url

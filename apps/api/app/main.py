import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient
from fastapi import FastAPI, Response, status
from psycopg import Error as PostgresError
from pydantic import BaseModel

from app.config import get_settings

_LOCAL_AZURITE_ACCOUNT_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
)


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(HealthResponse):
    dependencies: dict[str, str]
    unverified: list[str]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Reject invalid production and local-test configuration before serving traffic."""
    get_settings()
    yield


app = FastAPI(
    title="Job Tracking API",
    summary="API foundation for the career workspace.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Keep the process alive independently from optional infrastructure."""
    return HealthResponse(status="ok", service="job-tracking-api")


async def _can_connect(url: str, default_port: int) -> bool:
    try:
        parsed = urlparse(url)
        if not parsed.hostname:
            return False
        port = parsed.port or default_port
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(parsed.hostname, port), timeout=1.5
        )
        writer.close()
        await writer.wait_closed()
    except (OSError, TimeoutError, ValueError):
        return False
    return True


def _can_authenticate_postgres(url: str) -> bool:
    """Verify the configured Postgres credentials using a read-only query."""
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except (PostgresError, OSError, ValueError):
        return False


def _can_authorize_local_blob(endpoint: str) -> bool:
    """Verify the local Azurite emulator using its public test account only."""
    try:
        client = BlobServiceClient(
            account_url=endpoint,
            credential=_LOCAL_AZURITE_ACCOUNT_KEY,
            api_version="2023-11-03",
            connection_timeout=2,
            read_timeout=2,
            retry_total=0,
        )
        client.get_service_properties()
        return True
    except (AzureError, OSError, ValueError):
        return False


@app.get("/health/live", response_model=HealthResponse, tags=["health"])
async def liveness() -> HealthResponse:
    """Return process liveness without depending on infrastructure."""
    return HealthResponse(status="ok", service="job-tracking-api")


@app.get("/health/ready", response_model=ReadinessResponse, tags=["health"])
async def readiness(response: Response) -> ReadinessResponse:
    """Check local service authentication without mutating application data."""
    settings = get_settings()
    if settings.app_env in {"local", "test"}:
        postgres_ready, blob_ready = await asyncio.gather(
            asyncio.to_thread(_can_authenticate_postgres, settings.database_url),
            asyncio.to_thread(_can_authorize_local_blob, settings.blob_endpoint_url),
        )
        dependencies = {
            "postgresql_authentication": "ok" if postgres_ready else "unavailable",
            "blob_storage_authorization": "ok" if blob_ready else "unavailable",
        }
        ready = postgres_ready and blob_ready
        unverified = ["database_schema_compatibility"]
    else:
        postgres_reachable, blob_reachable = await asyncio.gather(
            _can_connect(settings.database_url, 5432),
            _can_connect(settings.blob_endpoint_url, 10000),
        )
        dependencies = {
            "postgresql_tcp": "reachable" if postgres_reachable else "unavailable",
            "blob_storage_tcp": "reachable" if blob_reachable else "unavailable",
        }
        ready = False
        unverified = [
            "postgresql_authentication",
            "database_schema_compatibility",
            "blob_storage_authorization",
        ]

    response.status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        service="job-tracking-api",
        dependencies=dependencies,
        unverified=unverified,
    )

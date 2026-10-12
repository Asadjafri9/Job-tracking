import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Response, status
from pydantic import BaseModel

from app.config import get_settings


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


@app.get("/health/live", response_model=HealthResponse, tags=["health"])
async def liveness() -> HealthResponse:
    """Return process liveness without depending on infrastructure."""
    return HealthResponse(status="ok", service="job-tracking-api")


@app.get("/health/ready", response_model=ReadinessResponse, tags=["health"])
async def readiness(response: Response) -> ReadinessResponse:
    """Check that configured local backing services accept connections."""
    settings = get_settings()
    results = await asyncio.gather(
        _can_connect(settings.database_url, 5432),
        _can_connect(settings.blob_endpoint_url, 10000),
    )
    dependencies = {
        "postgresql_tcp": "reachable" if results[0] else "unavailable",
        "blob_storage_tcp": "reachable" if results[1] else "unavailable",
    }
    # A listening port does not prove database credentials, schema compatibility,
    # or blob authorization. Keep readiness closed until those adapters exist.
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="not_ready",
        service="job-tracking-api",
        dependencies=dependencies,
        unverified=[
            "postgresql_authentication",
            "database_schema_compatibility",
            "blob_storage_authorization",
        ],
    )

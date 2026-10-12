import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from uuid import UUID, uuid4

from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import Error as PostgresError
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint

from app.config import get_settings
from app.contracts import (
    API_CONTRACT_VERSION,
    ERROR_RESPONSES,
    MINIMUM_COMPATIBLE_CLIENT_VERSION,
    ApiMetaResponse,
    ErrorField,
    error_response,
)

_LOCAL_AZURITE_ACCOUNT_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
)
_CLIENT_VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


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
    summary="Versioned API for the career workspace.",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url=None,
    lifespan=lifespan,
)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))


def _safe_http_error(status_code: int) -> tuple[str, str]:
    public_errors = {
        401: ("unauthenticated", "Authentication is required."),
        403: ("forbidden", "The request is not permitted."),
        404: ("not_found", "The requested resource was not found."),
        409: ("conflict", "The request conflicts with current state."),
        410: ("gone", "The requested resource is no longer available."),
        413: ("payload_too_large", "The request exceeds its size limit."),
        422: ("validation_error", "The request failed validation."),
        426: ("incompatible_contract_version", "This client contract version is not supported."),
        429: ("rate_limited", "The request limit was reached."),
        502: ("upstream_error", "An upstream service failed."),
        503: ("service_unavailable", "A required service is unavailable."),
    }
    return public_errors.get(
        status_code, ("http_error", "The request could not be completed.")
    )


def _is_compatible_client_version(version: str) -> bool:
    """Accept strict numeric MAJOR.MINOR.PATCH versions at or above the advertised minimum."""
    match = _CLIENT_VERSION_PATTERN.fullmatch(version)
    if match is None:
        return False
    try:
        supplied = tuple(int(part) for part in match.groups())
        minimum = tuple(int(part) for part in MINIMUM_COMPATIBLE_CLIENT_VERSION.split("."))
    except ValueError:
        return False
    return supplied >= minimum


@app.middleware("http")
async def identify_and_check_contract(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Attach a safe request ID and reject explicitly incompatible extension contracts."""
    supplied_id = request.headers.get("X-Request-ID", "")
    try:
        request_id = str(UUID(supplied_id))
    except (ValueError, AttributeError):
        request_id = str(uuid4())
    request.state.request_id = request_id

    response: Response
    contract_header = request.headers.get("X-Copilot-Contract-Version")
    client_version_header = request.headers.get("X-Copilot-Client-Version")
    incompatible_contract = False
    if request.url.path.startswith("/api/") and contract_header is not None:
        try:
            client_contract = int(contract_header)
        except ValueError:
            client_contract = -1
        incompatible_contract = client_contract != API_CONTRACT_VERSION
    incompatible_client = (
        request.url.path.startswith("/api/")
        and client_version_header is not None
        and not _is_compatible_client_version(client_version_header)
    )
    if incompatible_contract or incompatible_client:
        error_code, error_message = (
            (
                "incompatible_contract_version",
                "This client contract version is not supported.",
            )
            if incompatible_contract
            else ("incompatible_client_version", "This client version is not supported.")
        )
        payload = error_response(
            code=error_code,
            message=error_message,
            request_id=request_id,
        )
        response = JSONResponse(
            status_code=status.HTTP_426_UPGRADE_REQUIRED,
            content=payload.model_dump(mode="json"),
        )
    else:
        response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    is_api_documentation = request.url.path == "/api/v1/docs" or request.url.path.startswith(
        "/api/v1/docs/"
    )
    if (
        request.url.path.startswith("/api/")
        and not is_api_documentation
        and response.status_code == status.HTTP_404_NOT_FOUND
        and content_type.startswith("text/html")
    ):
        payload = error_response(
            code="not_found",
            message="The requested resource was not found.",
            request_id=request_id,
        )
        response = JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=payload.model_dump(mode="json"),
        )
    response.headers["X-Request-ID"] = request_id
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = _safe_http_error(exc.status_code)
    payload = error_response(code=code, message=message, request_id=_request_id(request))
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(mode="json"),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors = []
    for issue in exc.errors():
        location = [str(part) for part in issue.get("loc", ()) if part != "body"]
        issue_type = str(issue.get("type", "invalid"))
        if issue_type == "missing":
            field_code, field_message = "required", "This field is required."
        elif issue_type.endswith("_parsing") or issue_type.endswith("_type"):
            field_code, field_message = "invalid_type", "This field has an invalid type."
        else:
            field_code, field_message = "invalid", "This field is invalid."
        field_errors.append(
            ErrorField(field=".".join(location), code=field_code, message=field_message)
        )
    payload = error_response(
        code="validation_error",
        message="The request failed validation.",
        request_id=_request_id(request),
        field_errors=field_errors,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=payload.model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, _: Exception) -> JSONResponse:
    payload = error_response(
        code="internal_error",
        message="An unexpected server error occurred.",
        request_id=_request_id(request),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=payload.model_dump(mode="json"),
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


@app.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        **ERROR_RESPONSES,
        503: {
            "model": ReadinessResponse,
            "description": "A required dependency is unavailable.",
        },
    },
    tags=["health"],
)
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


@app.get(
    "/api/v1/meta",
    response_model=ApiMetaResponse,
    responses=ERROR_RESPONSES,
    tags=["meta"],
)
async def api_meta() -> ApiMetaResponse:
    """Expose compatibility metadata without exposing environment or secret values."""
    return ApiMetaResponse(
        api_version="v1",
        contract_version=API_CONTRACT_VERSION,
        minimum_compatible_client_version=MINIMUM_COMPATIBLE_CLIENT_VERSION,
    )

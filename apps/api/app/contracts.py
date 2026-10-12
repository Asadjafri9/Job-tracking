"""Stable, versioned API response contracts shared by routes and handlers."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

API_CONTRACT_VERSION: Literal[1] = 1
MINIMUM_COMPATIBLE_CLIENT_VERSION = "0.1.0"


class ErrorField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    code: str
    message: str


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: UUID
    field_errors: list[ErrorField]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


class ApiMetaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_version: Literal["v1"]
    contract_version: Literal[1]
    minimum_compatible_client_version: str


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication is required."},
    403: {"model": ErrorResponse, "description": "The request is not permitted."},
    404: {"model": ErrorResponse, "description": "The resource was not found."},
    409: {"model": ErrorResponse, "description": "The request conflicts with current state."},
    410: {"model": ErrorResponse, "description": "The resource is no longer available."},
    413: {"model": ErrorResponse, "description": "The request exceeds its size limit."},
    422: {"model": ErrorResponse, "description": "The request failed validation."},
    426: {"model": ErrorResponse, "description": "The client contract version is incompatible."},
    429: {"model": ErrorResponse, "description": "The request limit was reached."},
    500: {"model": ErrorResponse, "description": "An unexpected server error occurred."},
    502: {"model": ErrorResponse, "description": "An upstream service failed."},
    503: {"model": ErrorResponse, "description": "A required service is unavailable."},
}


def error_response(
    *,
    code: str,
    message: str,
    request_id: str,
    field_errors: list[ErrorField] | None = None,
) -> ErrorResponse:
    """Build the public error shape without copying arbitrary exception details."""
    return ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=UUID(request_id),
            field_errors=field_errors or [],
        )
    )

import json
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from starlette.routing import Route

from app.config import get_settings
from app.main import app, handle_unexpected_error, handle_validation_error


def local_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "APP_ENV": "local",
        "DATABASE_URL": "postgresql://runtime:local@127.0.0.1:55432/jobtracking",
        "MIGRATION_DATABASE_URL": "postgresql://migrator:local@127.0.0.1:55432/jobtracking",
        "BLOB_ENDPOINT_URL": "http://127.0.0.1:11000/devstoreaccount1",
        "OIDC_ISSUER": "http://127.0.0.1:18101/oidc",
        "OIDC_CLIENT_ID": "job-tracking-local",
        "OIDC_CLIENT_SECRET": "mock-client-secret",
        "OIDC_REDIRECT_URI": "http://127.0.0.1:18000/auth/callback",
        "LOCAL_MOCKS_ENABLED": "true",
        "CREDENTIAL_KEK_PROVIDER": "local",
        "CREDENTIAL_KEK_BASE64": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


def test_meta_exposes_version_without_environment_details(monkeypatch: pytest.MonkeyPatch) -> None:
    local_environment(monkeypatch)
    with TestClient(app) as client:
        response = client.get("/api/v1/meta")
    assert response.status_code == 200
    assert response.json() == {
        "api_version": "v1",
        "contract_version": 1,
        "minimum_compatible_client_version": "0.1.0",
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
    get_settings.cache_clear()


def test_incompatible_contract_is_a_standard_426_error(monkeypatch: pytest.MonkeyPatch) -> None:
    local_environment(monkeypatch)
    request_id = str(uuid4())
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/meta",
            headers={
                "X-Copilot-Contract-Version": "2",
                "X-Request-ID": request_id,
            },
        )
    assert response.status_code == 426
    assert response.headers["x-request-id"] == request_id
    assert response.json() == {
        "error": {
            "code": "incompatible_contract_version",
            "message": "This client contract version is not supported.",
            "request_id": request_id,
            "field_errors": [],
        }
    }
    assert response.headers["cache-control"] == "no-store"
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("client_version", "expected_status"),
    [
        ("0.0.9", 426),
        ("0.1.0", 200),
        ("0.1.1", 200),
        ("1.0.0", 200),
        ("0.1", 426),
        ("01.1.0", 426),
        ("v0.1.0", 426),
        (" 0.1.0", 426),
        ("0.1.0\n", 426),
    ],
)
def test_client_version_header_enforces_format_and_minimum(
    monkeypatch: pytest.MonkeyPatch, client_version: str, expected_status: int
) -> None:
    local_environment(monkeypatch)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/meta",
            headers={"X-Copilot-Client-Version": client_version},
        )

    assert response.status_code == expected_status
    if expected_status == 426:
        assert response.json()["error"]["code"] == "incompatible_client_version"
        assert response.json()["error"]["field_errors"] == []
    else:
        assert response.json()["minimum_compatible_client_version"] == "0.1.0"
    get_settings.cache_clear()


@pytest.mark.parametrize("path", ["/api/v1/not-a-route", "/api/v2/meta"])
def test_unknown_api_routes_return_json_not_spa_html(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    local_environment(monkeypatch)
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "not_found"
    assert "text/html" not in response.text
    get_settings.cache_clear()


def test_api_boundary_only_converts_html_404_fallbacks_to_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_environment(monkeypatch)

    async def dashboard_fallback(_: Request) -> HTMLResponse:
        return HTMLResponse("<html>dashboard fallback</html>", status_code=404)

    async def successful_html(_: Request) -> HTMLResponse:
        return HTMLResponse("<html>success</html>", status_code=202)

    fallback = Route("/api/{unmatched:path}", dashboard_fallback)
    success = Route("/api/success-html", successful_html)
    app.router.routes.extend([success, fallback])
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/unknown-feature-route")
            success_response = client.get("/api/success-html")
    finally:
        app.router.routes.remove(fallback)
        app.router.routes.remove(success)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "not_found"
    assert "dashboard fallback" not in response.text
    assert success_response.status_code == 202
    assert success_response.headers["content-type"].startswith("text/html")
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_validation_errors_are_sanitized_and_use_the_shared_envelope() -> None:
    request_id = str(uuid4())
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/profile",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 123),
            "http_version": "1.1",
        }
    )
    request.state.request_id = request_id
    error = RequestValidationError(
        [
            {
                "type": "string_type",
                "loc": ("body", "resume", "name"),
                "msg": "Input should be a valid string",
                "input": "private-user-supplied-value",
            }
        ]
    )

    response = await handle_validation_error(request, error)
    body = json.loads(response.body)

    assert response.status_code == 422
    assert body == {
        "error": {
            "code": "validation_error",
            "message": "The request failed validation.",
            "request_id": request_id,
            "field_errors": [
                {
                    "field": "resume.name",
                    "code": "invalid_type",
                    "message": "This field has an invalid type.",
                }
            ],
        }
    }
    assert "private-user-supplied-value" not in response.body.decode()


@pytest.mark.anyio
async def test_unexpected_errors_hide_exception_details() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/meta",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 123),
            "http_version": "1.1",
        }
    )
    request.state.request_id = str(uuid4())
    response = await handle_unexpected_error(request, RuntimeError("private exception detail"))

    assert response.status_code == 500
    assert b"private exception detail" not in response.body
    assert json.loads(response.body)["error"]["code"] == "internal_error"


def test_openapi_declares_versioned_meta_and_shared_error_models() -> None:
    schema = app.openapi()
    meta = schema["paths"]["/api/v1/meta"]["get"]
    assert schema["openapi"].startswith("3.")
    assert meta["responses"]["426"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ErrorResponse"
    )
    components = schema["components"]["schemas"]
    assert set(components["ErrorDetail"]["properties"]) == {
        "code",
        "message",
        "request_id",
        "field_errors",
    }

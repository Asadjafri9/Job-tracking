"""Stubbed provider adapter checks (AI-002): no live provider access."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.ai.providers import (
    GeminiAdapter,
    OpenRouterAdapter,
    ProviderAdapter,
    XaiAdapter,
)

EXTRACTION_REQUEST = {
    "document_type": "RESUME",
    "sections": [{"section_id": 0, "anchor": {}, "text": "Built systems at Example."}],
}


def _chat_response(payload: dict[str, Any], model: str = "m") -> dict[str, Any]:
    return {
        "id": "resp-1",
        "model": model,
        "choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
    }


ADAPTERS = [
    ("OPENROUTER", OpenRouterAdapter, "deepseek/deepseek-v4-flash", "https://openrouter.ai/api/v1"),
    ("XAI", XaiAdapter, "grok-4.7", "https://api.x.ai/v1"),
]


@pytest.mark.parametrize("provider,cls,model,base", ADAPTERS)
def test_chat_adapters_return_validated_success(
    provider: str, cls: Callable[[httpx.Client], ProviderAdapter], model: str, base: str
) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=_chat_response({"candidates": []}, model=model))

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=base)
    outcome = cls(client).call(
        kind="EXTRACTION",
        request=EXTRACTION_REQUEST,
        api_key="test-key",
        model_id=model,
        timeout_seconds=10,
    )
    assert outcome.kind == "SUCCESS"
    assert outcome.content == {"candidates": []}
    assert outcome.input_tokens == 12 and outcome.output_tokens == 7
    assert seen["url"] == f"{base}/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == model
    assert seen["body"]["response_format"]["json_schema"]["strict"] is True
    assert "api_key" not in json.dumps(seen["body"])


def test_openrouter_requests_privacy_routing() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_chat_response({"candidates": []}))

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://openrouter.ai/api/v1"
    )
    outcome = OpenRouterAdapter(client).call(
        kind="EXTRACTION",
        request=EXTRACTION_REQUEST,
        api_key="k",
        model_id="deepseek/deepseek-v4-flash",
        timeout_seconds=10,
    )
    assert outcome.kind == "SUCCESS"
    assert seen["body"]["provider"]["data_collection"] == "deny"


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (401, {"error": "bad key"}, "INVALID_KEY"),
        (403, {"error": "forbidden"}, "INVALID_KEY"),
        (402, {"error": "insufficient credits"}, "EXHAUSTED"),
        (429, {"error": "slow down"}, "RATE_LIMITED"),
        (503, {"error": "capacity"}, "UNAVAILABLE"),
        (400, {"error": "bad schema"}, "BAD_INPUT"),
    ],
)
def test_chat_adapters_normalize_error_states(
    status: int, body: dict[str, Any], expected: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"retry-after": "3"} if status == 429 else {}
        return httpx.Response(status, json=body, headers=headers)

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.x.ai/v1"
    )
    outcome = XaiAdapter(client).call(
        kind="EMAIL",
        request={
            "recipient_email": "a@b.co",
            "employer": "E",
            "role": "R",
            "job_excerpt": "",
            "facts": [],
            "tone_tips": [],
        },
        api_key="k",
        model_id="grok-4.7",
        timeout_seconds=10,
    )
    assert outcome.kind == expected
    if status == 429:
        assert outcome.retry_after_seconds == 3
        assert outcome.retriable_once is True


def test_timeout_maps_to_unknown_not_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.x.ai/v1"
    )
    outcome = XaiAdapter(client).call(
        kind="EXTRACTION",
        request=EXTRACTION_REQUEST,
        api_key="k",
        model_id="grok-4.7",
        timeout_seconds=1,
    )
    assert outcome.kind == "UNKNOWN"


def test_non_json_envelope_maps_to_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>oops</html>")

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.x.ai/v1"
    )
    outcome = XaiAdapter(client).call(
        kind="EXTRACTION",
        request=EXTRACTION_REQUEST,
        api_key="k",
        model_id="grok-4.7",
        timeout_seconds=10,
    )
    assert outcome.kind == "UNKNOWN"


def test_refusal_maps_to_refusal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": None, "refusal": "cannot comply"}}],
                "usage": {},
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.x.ai/v1"
    )
    outcome = XaiAdapter(client).call(
        kind="EXTRACTION",
        request=EXTRACTION_REQUEST,
        api_key="k",
        model_id="grok-4.7",
        timeout_seconds=10,
    )
    assert outcome.kind == "REFUSAL"


def test_unevaluated_model_rejected_before_dispatch() -> None:
    outcome = XaiAdapter().call(
        kind="EXTRACTION",
        request=EXTRACTION_REQUEST,
        api_key="k",
        model_id="grok-99-beta",
        timeout_seconds=10,
    )
    assert outcome.kind == "BAD_INPUT"


def test_gemini_adapter_uses_generate_content_schema() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["key"] = request.headers.get("x-goog-api-key")
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps({"candidates": []})}]}}
                ],
                "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 4},
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://generativelanguage.googleapis.com/v1beta",
    )
    outcome = GeminiAdapter(client).call(
        kind="EXTRACTION",
        request=EXTRACTION_REQUEST,
        api_key="gemini-key",
        model_id="gemini-3.8-flash",
        timeout_seconds=10,
    )
    assert outcome.kind == "SUCCESS"
    assert outcome.input_tokens == 9 and outcome.output_tokens == 4
    assert seen["url"].endswith("/models/gemini-3.8-flash:generateContent")
    assert seen["key"] == "gemini-key"
    config = seen["body"]["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert "additionalProperties" not in json.dumps(config["responseSchema"])


def test_gemini_error_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"}, headers={"retry-after": "2"})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://generativelanguage.googleapis.com/v1beta",
    )
    outcome = GeminiAdapter(client).call(
        kind="EXTRACTION",
        request=EXTRACTION_REQUEST,
        api_key="k",
        model_id="gemini-3.8-flash",
        timeout_seconds=10,
    )
    assert outcome.kind == "RATE_LIMITED"
    assert outcome.retry_after_seconds == 2
    assert outcome.retriable_once is True

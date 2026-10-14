"""Unit checks for the bounded public fetch boundary (MON-002)."""

from __future__ import annotations

import pytest

from app.monitoring.fetch import (
    MAX_REDIRECTS,
    Fetcher,
    FetchUnsupported,
    _is_public_ip,
    _netloc,
    _robots_allows,
    resolve_public_addresses,
    validate_public_url,
)


def test_validate_public_url_accepts_https_careers() -> None:
    target = validate_public_url("https://jobs.example.com/careers?ref=a#frag")
    assert target.host == "jobs.example.com"
    assert target.url == "https://jobs.example.com/careers?ref=a"


@pytest.mark.parametrize(
    "url",
    [
        "http://jobs.example.com/careers",
        "https://user:pw@jobs.example.com/careers",
        "https://127.0.0.1/careers",
        "https://[::1]/careers",
        "https://169.254.169.254/latest/meta-data",
        "https://jobs.example.com:8443/careers",
        "file:///etc/passwd",
        "https:///broken",
        "javascript:alert(1)",
    ],
)
def test_validate_public_url_rejects_unsafe(url: str) -> None:
    with pytest.raises(FetchUnsupported):
        validate_public_url(url)


@pytest.mark.parametrize(
    "address,expected",
    [
        ("8.8.8.8", True),
        ("10.0.0.1", False),
        ("192.168.1.1", False),
        ("172.16.0.1", False),
        ("127.0.0.1", False),
        ("169.254.169.254", False),
        ("::1", False),
        ("fd00::1", False),
        ("fe80::1", False),
        ("::ffff:10.0.0.1", False),
        ("0.0.0.0", False),
        ("224.0.0.1", False),
    ],
)
def test_is_public_ip(address: str, expected: bool) -> None:
    assert _is_public_ip(address) is expected


def test_resolve_rejects_private_answers() -> None:
    with pytest.raises(FetchUnsupported):
        resolve_public_addresses("internal.test", resolver=lambda _h: ["10.0.0.1"])


def test_resolve_rejects_mixed_answers() -> None:
    """Any non-global answer fails closed (DNS-rebinding guard)."""
    with pytest.raises(FetchUnsupported):
        resolve_public_addresses(
            "mixed.test", resolver=lambda _h: ["8.8.8.8", "192.168.0.1"]
        )


def test_resolve_accepts_all_public() -> None:
    addresses = resolve_public_addresses(
        "ok.test", resolver=lambda _h: ["8.8.8.8", "1.1.1.1"]
    )
    assert addresses == ["1.1.1.1", "8.8.8.8"]


def test_resolve_prefers_ipv4_over_ipv6() -> None:
    """IPv6 answers sort after IPv4 so the pinned address has IPv4 egress."""
    answers = ["2600:1f18::1", "8.8.8.8", "1.1.1.1"]
    addresses = resolve_public_addresses("dual.test", resolver=lambda _h: list(answers))
    assert addresses == ["1.1.1.1", "8.8.8.8", "2600:1f18::1"]
    # Resolver output order cannot influence the pinned address.
    reversed_resolver = lambda _h: list(reversed(answers))  # noqa: E731
    assert (
        resolve_public_addresses("dual.test", resolver=reversed_resolver) == addresses
    )


def test_resolve_rejects_unparseable_answer() -> None:
    """A non-IP resolver answer fails closed instead of reaching urlunsplit."""
    with pytest.raises(FetchUnsupported):
        resolve_public_addresses("bad.test", resolver=lambda _h: ["not-an-ip"])


def test_netloc_brackets_ipv6() -> None:
    assert _netloc("2600:1f18::1") == "[2600:1f18::1]"
    assert _netloc("8.8.8.8") == "8.8.8.8"


def test_robots_respects_disallow_and_allow() -> None:
    robots = (
        "User-agent: *\n"
        "Disallow: /private\n"
        "Allow: /private/public\n\n"
        "User-agent: RolevoJobMonitor\n"
        "Disallow: /careers/internal\n"
    )
    assert _robots_allows(robots, "/careers") is True
    assert _robots_allows(robots, "/private/x") is False
    assert _robots_allows(robots, "/careers/internal/jobs") is False


def test_robots_uses_most_specific_agent_group() -> None:
    robots = (
        "User-agent: *\nDisallow: /\n\nUser-agent: RolevoJobMonitor\nAllow: /careers\n"
    )
    assert _robots_allows(robots, "/careers") is True
    assert _robots_allows(robots, "/other") is False


def test_robots_groups_reset_correctly() -> None:
    robots = "User-agent: googlebot\nDisallow: /x\n\nUser-agent: *\nDisallow: /y\n"
    assert _robots_allows(robots, "/x") is True
    assert _robots_allows(robots, "/y") is False


def test_robots_union_denies_when_any_matching_group_disallows() -> None:
    # "rolevo" substring-matches our product token, so its group applies
    # alongside `*`; a disallow in either group denies the path.
    robots = (
        "User-agent: rolevo\nDisallow: /x\n\nUser-agent: *\nDisallow: /y\n"
    )
    assert _robots_allows(robots, "/x") is False
    assert _robots_allows(robots, "/y") is False
    assert _robots_allows(robots, "/z") is True


class _FakeResponse:
    def __init__(self, status: int, body: bytes = b"", headers: dict | None = None):
        self.status_code = status
        self.content = body
        self.headers = headers or {}
        self.text = body.decode("utf-8", errors="replace")
        self.is_redirect = status in {301, 302, 303, 307, 308}

    def iter_bytes(self, chunk_size: int) -> list[bytes]:
        return [
            self.content[i : i + chunk_size]
            for i in range(0, len(self.content), chunk_size)
        ]


class _StreamContext:
    def __init__(self, response: _FakeResponse):
        self._response = response

    def __enter__(self) -> _FakeResponse:
        return self._response

    def __exit__(self, *args: object) -> None:
        return None


class _FakeClient:
    def __init__(self, script: list[_FakeResponse]):
        self.script = list(script)
        self.requests: list[str] = []

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def stream(
        self, method: str, url: str, headers: dict | None = None, **kwargs: object
    ) -> _StreamContext:
        self.requests.append(url)
        return _StreamContext(self.script.pop(0))


def _fetcher_with(script: list[_FakeResponse], monkeypatch: pytest.MonkeyPatch) -> Fetcher:
    clients: list[_FakeClient] = []
    import httpx

    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: clients.append(_FakeClient(script)) or clients[-1]
    )
    fetcher = Fetcher(resolver=lambda _h: ["8.8.8.8"])
    return fetcher


def test_fetch_follows_bounded_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = _fetcher_with(
        [
            _FakeResponse(200, b""),  # robots
            _FakeResponse(301, headers={"location": "/jobs2"}),
            _FakeResponse(200, b"<html>ok</html>"),
        ],
        monkeypatch,
    )
    outcome = fetcher.fetch("https://jobs.example.com/careers")
    assert outcome.status == "OK"
    assert outcome.content == b"<html>ok</html>"


def test_fetch_rejects_too_many_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = _fetcher_with(
        [_FakeResponse(200, b"")]
        + [_FakeResponse(301, headers={"location": f"/hop{i}"}) for i in range(MAX_REDIRECTS + 2)],
        monkeypatch,
    )
    with pytest.raises(FetchUnsupported, match="redirect"):
        fetcher.fetch("https://jobs.example.com/careers")


def test_fetch_rejects_redirect_to_private(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = _fetcher_with(
        [
            _FakeResponse(200, b""),
            _FakeResponse(301, headers={"location": "https://127.0.0.1/x"}),
        ],
        monkeypatch,
    )
    with pytest.raises(FetchUnsupported):
        fetcher.fetch("https://jobs.example.com/careers")


def test_fetch_robots_disallow_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = _fetcher_with(
        [_FakeResponse(200, b"User-agent: *\nDisallow: /careers")],
        monkeypatch,
    )
    from app.monitoring.fetch import FetchDenied

    with pytest.raises(FetchDenied):
        fetcher.fetch("https://jobs.example.com/careers")


def test_fetch_honours_not_modified(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = _fetcher_with(
        [_FakeResponse(200, b""), _FakeResponse(304)],
        monkeypatch,
    )
    outcome = fetcher.fetch("https://jobs.example.com/careers", etag='"v1"')
    assert outcome.status == "NOT_MODIFIED"


def test_fetch_denied_on_403(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.monitoring.fetch import FetchDenied

    fetcher = _fetcher_with(
        [_FakeResponse(200, b""), _FakeResponse(403)],
        monkeypatch,
    )
    with pytest.raises(FetchDenied):
        fetcher.fetch("https://jobs.example.com/careers")


def test_fetch_failed_on_5xx_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.monitoring.fetch import FetchFailed

    fetcher = _fetcher_with(
        [_FakeResponse(200, b""), _FakeResponse(500, headers={"retry-after": "30"})],
        monkeypatch,
    )
    with pytest.raises(FetchFailed):
        fetcher.fetch("https://jobs.example.com/careers")


def test_fetch_enforces_byte_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.monitoring.fetch import MAX_BYTES

    fetcher = _fetcher_with(
        [_FakeResponse(200, b""), _FakeResponse(200, b"x" * (MAX_BYTES + 1))],
        monkeypatch,
    )
    with pytest.raises(FetchUnsupported, match="byte bound"):
        fetcher.fetch("https://jobs.example.com/careers")


def test_fetch_pins_connection_to_validated_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    clients: list[_FakeClient] = []
    import httpx

    client = _FakeClient([_FakeResponse(200, b""), _FakeResponse(200, b"ok")])
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: clients.append(client) or clients[-1]
    )
    fetcher = Fetcher(resolver=lambda _h: ["8.8.8.8"])
    outcome = fetcher.fetch("https://jobs.example.com/careers")
    assert outcome.status == "OK"
    assert all(url.startswith("https://8.8.8.8/") for url in clients[0].requests)


def test_fetch_brackets_ipv6_pinned_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """IPv6-only hosts must produce https://[v6]/... URLs, not a broken port."""
    import httpx

    client = _FakeClient([_FakeResponse(200, b""), _FakeResponse(200, b"ok")])
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client)
    fetcher = Fetcher(resolver=lambda _h: ["2600:1f18::1"])
    outcome = fetcher.fetch("https://jobs.example.com/careers")
    assert outcome.status == "OK"
    assert all(url.startswith("https://[2600:1f18::1]/") for url in client.requests)


def test_robots_cache_obeys_injected_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Robots TTL expiry follows the fetcher's clock, not wall time."""
    import time

    import httpx

    from app.monitoring.fetch import ROBOTS_TTL_SECONDS

    now = [0.0]
    # The throttle sleeps via time.sleep; advance the fake clock so it exits.
    monkeypatch.setattr(time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    client = _FakeClient([_FakeResponse(200, b"")] * 3 + [_FakeResponse(200, b"ok")] * 3)
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client)
    fetcher = Fetcher(resolver=lambda _h: ["8.8.8.8"], clock=lambda: now[0])

    fetcher.fetch("https://jobs.example.com/careers")
    assert len(client.requests) == 2  # robots + content

    fetcher.fetch("https://jobs.example.com/careers")
    assert len(client.requests) == 3  # cached robots, content only

    now[0] += ROBOTS_TTL_SECONDS + 1
    fetcher.fetch("https://jobs.example.com/careers")
    assert len(client.requests) == 5  # robots refetched after TTL expiry

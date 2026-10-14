"""Bounded, SSRF-guarded public fetching for career-page monitoring.

Only explicit public HTTPS destinations are fetched: no userinfo, no IP
literals, no non-HTTP schemes. Every A/AAAA answer must be a globally
routable address and the connection is pinned to a validated address with
correct TLS SNI. Redirects are revalidated per hop (max three). robots.txt
is honored for our crawler identity, responses are byte- and time-bounded,
and the same host is throttled to one fetch per two seconds.

No JavaScript, no login, no CAPTCHA bypass: explicit denial surfaces as
DENIED rather than a workaround.
"""

from __future__ import annotations

import hashlib
import ipaddress
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import httpx

USER_AGENT = "RolevoJobMonitor/1.0 (+https://github.com/Asadjafri9/Job-tracking)"
MAX_REDIRECTS = 3
MAX_BYTES = 2 * 1024 * 1024
FETCH_DEADLINE_SECONDS = 30.0
ROBOTS_TTL_SECONDS = 24 * 60 * 60
HOST_THROTTLE_SECONDS = 2.0
MAX_CONTENT_REQUESTS = 3


class FetchDenied(Exception):
    """robots.txt or an explicit access control denied the fetch."""


class FetchUnsupported(Exception):
    """The URL cannot be fetched within the public boundary."""


class FetchFailed(Exception):
    """Transient network or protocol failure (retriable within the run)."""


def _is_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


@dataclass(frozen=True)
class PublicTarget:
    url: str
    host: str
    port: int


def validate_public_url(raw: str) -> PublicTarget:
    try:
        parts = urlsplit(raw.strip())
    except ValueError as exc:
        raise FetchUnsupported("source URL is not parseable") from exc
    if parts.scheme != "https":
        raise FetchUnsupported("only https sources are supported")
    if parts.username or parts.password:
        raise FetchUnsupported("credentials in URLs are not allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise FetchUnsupported("source URL needs a host")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise FetchUnsupported("IP-literal sources are not allowed")
    port = parts.port or 443
    if port != 443:
        raise FetchUnsupported("only port 443 is supported")
    clean = urlunsplit(("https", parts.netloc.lower(), parts.path or "/", parts.query, ""))
    return PublicTarget(url=clean, host=host, port=443)


def resolve_public_addresses(
    host: str, resolver: Callable[[str], list[str]] | None = None
) -> list[str]:
    resolve = resolver or (
        lambda name: [
            str(item[4][0])
            for item in socket.getaddrinfo(name, 443, proto=socket.IPPROTO_TCP)
        ]
    )

    def sort_key(address: str) -> tuple[int, str]:
        try:
            return (ipaddress.ip_address(address).version, address)
        except ValueError:
            return (99, address)

    try:
        # IPv4 first: the worker may lack IPv6 egress.
        addresses = sorted(set(resolve(host)), key=sort_key)
    except (OSError, socket.gaierror) as exc:
        raise FetchFailed(f"DNS resolution failed for {host}") from exc
    if not addresses:
        raise FetchFailed(f"DNS returned no addresses for {host}")
    bad = [address for address in addresses if not _is_public_ip(address)]
    if bad:
        raise FetchUnsupported(
            f"DNS for {host} resolves to non-public addresses"
        )
    return addresses


def _netloc(ip: str) -> str:
    return f"[{ip}]" if ipaddress.ip_address(ip).version == 6 else ip


def _robots_allows(robots_text: str, path: str) -> bool:
    """Minimal RFC 9309 evaluation for our product token plus `*`."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for line in robots_text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()
        if field_name == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents = []
                rules = []
            agents.append(value.lower())
        elif field_name in {"allow", "disallow"} and agents:
            rules.append((field_name, value))
    if rules or agents:
        groups.append((agents, rules))
    # Conservative union of every matching group (our token and `*`): the
    # longest matching pattern wins and a disallow never loses a tie.
    matching_rules: list[tuple[str, str]] = []
    for group_agents, group_rules in groups:
        if any(agent == "*" or agent.lower() in USER_AGENT.lower() for agent in group_agents):
            matching_rules.extend(group_rules)
    longest: tuple[int, str] = (-1, "allow")
    for kind, pattern in matching_rules:
        if not pattern or not path.startswith(pattern):
            continue
        if len(pattern) > longest[0] or (len(pattern) == longest[0] and kind == "disallow"):
            longest = (len(pattern), kind)
    return longest[1] != "disallow"


@dataclass
class FetchOutcome:
    status: str  # OK | NOT_MODIFIED | DENIED | UNSUPPORTED | FAILED
    url: str
    content: bytes | None = None
    content_type: str | None = None
    etag: str | None = None
    content_hash: str | None = None
    detail: str | None = None


@dataclass
class Fetcher:
    """Safe fetcher with injectable transport/resolver for tests."""

    resolver: Callable[[str], list[str]] | None = None
    robots_cache: dict[str, tuple[float, str]] = field(default_factory=dict)
    host_last_fetch: dict[str, float] = field(default_factory=dict)
    clock: Callable[[], float] = time.monotonic
    timeout: float = FETCH_DEADLINE_SECONDS

    def _throttle(self, host: str) -> None:
        last = self.host_last_fetch.get(host)
        now = self.clock()
        if last is not None and now - last < HOST_THROTTLE_SECONDS:
            delay = HOST_THROTTLE_SECONDS - (now - last)
            deadline = self.clock() + delay
            while self.clock() < deadline:
                time.sleep(min(0.05, deadline - self.clock()))
        self.host_last_fetch[host] = self.clock()

    def _read_bounded(self, response: httpx.Response) -> bytes:
        """Read at most MAX_BYTES+1 bytes; excess fails the bound check."""
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes(65536):
            total += len(chunk)
            if total > MAX_BYTES:
                raise FetchUnsupported("response exceeded the byte bound")
            chunks.append(chunk)
        return b"".join(chunks)

    def _robots(self, host: str, client: httpx.Client, ip: str) -> str:
        cached = self.robots_cache.get(host)
        if cached is not None and self.clock() - cached[0] < ROBOTS_TTL_SECONDS:
            return cached[1]
        self._throttle(host)
        try:
            with client.stream(
                "GET",
                f"https://{_netloc(ip)}/robots.txt",
                headers={"Host": host, "User-Agent": USER_AGENT},
                extensions={"sni_hostname": host},
                timeout=self.timeout,
            ) as response:
                text = (
                    self._read_bounded(response).decode("utf-8", errors="replace")
                    if response.status_code == 200
                    else ""
                )
        except FetchUnsupported:
            raise
        except httpx.HTTPError as exc:
            raise FetchFailed(f"robots fetch failed for {host}") from exc
        self.robots_cache[host] = (self.clock(), text)
        return text

    def fetch(self, raw_url: str, etag: str | None = None) -> FetchOutcome:
        target = validate_public_url(raw_url)
        addresses = resolve_public_addresses(target.host, self.resolver)
        ip = addresses[0]
        headers = {
            "Host": target.host,
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/rss+xml,application/atom+xml,application/json;q=0.8",
        }
        if etag:
            headers["If-None-Match"] = etag
        try:
            with httpx.Client(
                follow_redirects=False,
                max_redirects=0,
            ) as client:
                robots = self._robots(target.host, client, ip)
                path = urlsplit(target.url).path or "/"
                if not _robots_allows(robots, path):
                    raise FetchDenied(f"robots.txt disallows {target.host}{path}")
                self._throttle(target.host)
                url, host, ip_address = target.url, target.host, ip
                for _hop in range(MAX_REDIRECTS + 1):
                    parts = urlsplit(url)
                    pinned = urlunsplit(
                        ("https", _netloc(ip_address), parts.path or "/", parts.query, "")
                    )
                    try:
                        with client.stream(
                            "GET",
                            pinned,
                            headers={**headers, "Host": host},
                            extensions={"sni_hostname": host},
                            timeout=self.timeout,
                        ) as response:
                            status = response.status_code
                            location = response.headers.get("location", "")
                            content_type = response.headers.get("content-type")
                            etag = response.headers.get("etag")
                            retry_after = response.headers.get("retry-after")
                            body: bytes | None = None
                            if status == 200:
                                body = self._read_bounded(response)
                    except FetchUnsupported:
                        raise
                    except httpx.HTTPError as exc:
                        raise FetchFailed(f"fetch failed for {target.url}") from exc
                    if status in {301, 302, 303, 307, 308}:
                        if not location:
                            raise FetchFailed("redirect without a location")
                        relative = location if location.startswith("/") else f"/{location}"
                        joined = location if "://" in location else f"https://{host}{relative}"
                        nxt = validate_public_url(joined)
                        addresses = resolve_public_addresses(nxt.host, self.resolver)
                        url, host, ip_address = nxt.url, nxt.host, addresses[0]
                        if host != target.host:
                            robots = self._robots(host, client, ip_address)
                            next_path = urlsplit(url).path or "/"
                            if not _robots_allows(robots, next_path):
                                raise FetchDenied(
                                    f"robots.txt disallows redirect to {host}{next_path}"
                                )
                            self._throttle(host)
                        continue
                    if status == 304:
                        return FetchOutcome(status="NOT_MODIFIED", url=target.url)
                    if status in {401, 403}:
                        raise FetchDenied(
                            f"{target.host} denied the fetch (HTTP {status})"
                        )
                    if status == 429:
                        raise FetchFailed(
                            f"{target.host} rate limited the fetch "
                            f"(retry-after: {retry_after or 'unspecified'})"
                        )
                    if status >= 500:
                        raise FetchFailed(f"{target.host} returned HTTP {status}")
                    if status != 200 or body is None:
                        raise FetchUnsupported(f"{target.host} returned HTTP {status}")
                    return FetchOutcome(
                        status="OK",
                        url=target.url,
                        content=body,
                        content_type=content_type,
                        etag=etag,
                        content_hash=hashlib.sha256(body).hexdigest(),
                    )
                raise FetchUnsupported("too many redirects")
        except (FetchDenied, FetchUnsupported):
            raise

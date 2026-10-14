"""Bounded listing extraction from fetched public pages (MON-002/003).

Structured data wins: JobPosting JSON-LD and RSS/Atom items. Rendered HTML
falls back to bounded anchor/link extraction with source anchors. The
extractor never invents jobs, URLs, or dates — only observed links and text
are returned.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

MAX_CANDIDATES = 200
MAX_TITLE = 255
MAX_TEXT = 500_000
_JOBISH = re.compile(
    r"(job|career|position|opening|vacanc|apply|role|posting)", re.IGNORECASE
)


@dataclass
class JobCandidate:
    external_id: str | None
    title: str
    employer: str | None
    url: str | None
    location: str | None = None
    is_remote: bool | None = None
    posted_at: str | None = None
    anchors: list[dict[str, str]] = field(default_factory=list)


def _bounded(value: str | None, limit: int = MAX_TITLE) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned[:limit] or None


def _absolute(url: str | None, base: str) -> str | None:
    if not url:
        return None
    joined = urljoin(base, url)
    if urlsplit(joined).scheme != "https":
        return None
    return joined[:2048]


class _JsonLdFinder(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_script = False
        self._chunks: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        types = dict(attrs).get("type", "") or ""
        if "ld+json" in types:
            self._in_script = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_script:
            self.blocks.append("".join(self._chunks)[:MAX_TEXT])
            self._in_script = False


def _jsonld_candidates(node: object, base: str) -> list[JobCandidate]:
    found: list[JobCandidate] = []
    if isinstance(node, dict):
        types = node.get("@type") or node.get("type") or []
        if isinstance(types, str):
            types = [types]
        if "JobPosting" in types:
            hiring = node.get("hiringOrganization") or {}
            if isinstance(hiring, dict):
                hiring = hiring.get("name")
            location = node.get("jobLocation") or {}
            if isinstance(location, dict):
                address = location.get("address") or {}
                if isinstance(address, dict):
                    location = ", ".join(
                        part
                        for part in (
                            address.get("addressLocality"),
                            address.get("addressRegion"),
                            address.get("addressCountry")
                            if isinstance(address.get("addressCountry"), str)
                            else (address.get("addressCountry") or {}).get("name"),
                        )
                        if part
                    )
                else:
                    location = str(address)
            remote = node.get("jobLocationType")
            found.append(
                JobCandidate(
                    external_id=_bounded(node.get("identifier") and str(
                        (node["identifier"] or {}).get("value")
                        if isinstance(node["identifier"], dict)
                        else node["identifier"]
                    )),
                    title=_bounded(node.get("title")) or "Untitled role",
                    employer=_bounded(hiring if isinstance(hiring, str) else None),
                    url=_absolute(node.get("url") or node.get("directApplyUrl"), base),
                    location=_bounded(location if isinstance(location, str) else None),
                    is_remote=(
                        True
                        if isinstance(remote, str)
                        and any(t in remote.lower() for t in ("remote", "telecommute"))
                        else None
                    ),
                    posted_at=_bounded(node.get("datePosted")),
                    anchors=[{"kind": "json-ld", "ref": "JobPosting"}],
                )
            )
        for key in ("@graph", "itemListElement", "hasPart"):
            child = node.get(key)
            if isinstance(child, (list, dict)):
                found.extend(_jsonld_candidates(child, base))
        if isinstance(node.get("item"), dict):
            found.extend(_jsonld_candidates(node["item"], base))
    elif isinstance(node, list):
        for item in node[:MAX_CANDIDATES]:
            found.extend(_jsonld_candidates(item, base))
    return found


def _rss_candidates(content: bytes, base: str) -> list[JobCandidate]:
    found: list[JobCandidate] = []
    try:
        root = ElementTree.fromstring(content[:MAX_TEXT])
    except ElementTree.ParseError:
        return found
    items = root.findall(".//item") or root.findall(
        ".//{http://www.w3.org/2005/Atom}entry"
    )
    atom = "{http://www.w3.org/2005/Atom}"
    for index, item in enumerate(items[:MAX_CANDIDATES]):

        def text_of(*names: str, node: ElementTree.Element = item) -> str | None:
            for name in names:
                found = node.find(name)
                if found is None:
                    found = node.find(f"{atom}{name}")
                if found is not None and found.text:
                    return str(found.text)
            return None

        title = text_of("title", "dc:title", "{http://purl.org/dc/elements/1.1/}title")
        link = text_of("link", "guid")
        link_node = item.find(f"{atom}link")
        if link is None and link_node is not None:
            link = link_node.get("href")
        if not title:
            continue
        found.append(
            JobCandidate(
                external_id=_bounded(text_of("guid", "id")),
                title=_bounded(title) or "Untitled role",
                employer=_bounded(text_of("author", "name", "company")),
                url=_absolute(link, base),
                location=_bounded(text_of("location")),
                posted_at=_bounded(text_of("pubDate", "published", "updated")),
                anchors=[{"kind": "feed", "ref": f"item[{index}]"}],
            )
        )
    return found


class _LinkExtractor(HTMLParser):
    def __init__(self, base: str, region_selector: str | None) -> None:
        super().__init__()
        self.base = base
        self.region_selector = (region_selector or "").lstrip("#.").strip() or None
        self.links: list[JobCandidate] = []
        self._current: str | None = None
        self._text: list[str] = []
        self._depth = 0
        self._in_region = self.region_selector is None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag == "a" and self._in_region:
            self._current = attrs_map.get("href")
            self._text = []
        # A region selector is matched against id/class tokens; links outside
        # the marked region are ignored when one is configured.
        marker = f"{attrs_map.get('id', '')} {attrs_map.get('class', '')}".strip()
        if (
            not self._in_region
            and self.region_selector
            and tag in {"ul", "ol", "section", "div", "main"}
            and self.region_selector in marker.split()
        ):
            self._in_region = True
            self._depth = 1
        elif self._depth:
            self._depth += 1

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current is not None:
            title = _bounded(" ".join(self._text))
            url = _absolute(self._current, self.base)
            if title and url and _JOBISH.search(f"{title} {self._current}"):
                self.links.append(
                    JobCandidate(
                        external_id=None,
                        title=title,
                        employer=None,
                        url=url,
                        anchors=[{"kind": "html-anchor", "ref": self._current[:256]}],
                    )
                )
            self._current = None
        if self._depth:
            self._depth -= 1
            if self._depth == 0 and self._in_region:
                self._in_region = False


def extract_candidates(
    content: bytes, content_type: str | None, base_url: str, region_selector: str | None = None
) -> tuple[list[JobCandidate], str]:
    """Return (candidates, method); never raises on unparseable content."""
    text = content[:MAX_TEXT]
    ctype = (content_type or "").lower()
    if "xml" in ctype or "rss" in ctype or "atom" in ctype or text.lstrip().startswith(b"<"):
        feed = _rss_candidates(text, base_url)
        if feed:
            return feed[:MAX_CANDIDATES], "feed"
    if b"ld+json" in text or b"application/ld" in text:
        ld_parser = _JsonLdFinder()
        try:
            ld_parser.feed(text.decode("utf-8", errors="replace"))
        except Exception:
            pass
        found: list[JobCandidate] = []
        for block in ld_parser.blocks:
            try:
                found.extend(_jsonld_candidates(json.loads(block), base_url))
            except (json.JSONDecodeError, TypeError):
                continue
            if len(found) >= MAX_CANDIDATES:
                break
        if found:
            return found[:MAX_CANDIDATES], "json-ld"
    parser = _LinkExtractor(base_url, region_selector)
    try:
        parser.feed(text.decode("utf-8", errors="replace"))
    except Exception:
        pass
    return parser.links[:MAX_CANDIDATES], "html-anchors"

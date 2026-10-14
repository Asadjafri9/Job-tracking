"""Unit checks for bounded listing extraction (MON-002)."""

from __future__ import annotations

import json

from app.monitoring.extract import MAX_CANDIDATES, extract_candidates


def test_jsonld_jobposting_extracted() -> None:
    html = b"""
    <html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"JobPosting",
     "title":"Backend Engineer",
     "hiringOrganization":{"@type":"Organization","name":"Example Corp"},
     "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress",
        "addressLocality":"Berlin","addressCountry":"DE"}},
     "jobLocationType":"TELECOMMUTE",
     "identifier":{"@type":"PropertyValue","value":"req-42"},
     "url":"https://jobs.example.com/jobs/req-42?utm_source=x",
     "datePosted":"2026-10-01"}
    </script></head><body></body></html>
    """
    found, method = extract_candidates(html, "text/html", "https://jobs.example.com/")
    assert method == "json-ld"
    assert len(found) == 1
    job = found[0]
    assert job.title == "Backend Engineer"
    assert job.employer == "Example Corp"
    assert job.external_id == "req-42"
    assert job.is_remote is True
    assert job.location == "Berlin, DE"
    assert job.posted_at == "2026-10-01"


def test_jsonld_graph_multiple_postings() -> None:
    graph = {"@graph": [{"@type": "JobPosting", "title": f"Role {i}"} for i in range(3)]}
    html = (
        b'<script type="application/ld+json">'
        + json.dumps(graph).encode()
        + b"</script>"
    )
    found, method = extract_candidates(html, "text/html", "https://a.example/")
    assert method == "json-ld"
    assert [job.title for job in found] == ["Role 0", "Role 1", "Role 2"]


def test_rss_feed_items() -> None:
    rss = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>Senior Designer</title>
        <link>https://jobs.example.com/j/9</link>
        <guid>feed-9</guid><pubDate>Tue, 01 Oct 2026 09:00:00 GMT</pubDate></item>
      <item><title>PM</title><link>https://jobs.example.com/j/10</link><guid>feed-10</guid></item>
    </channel></rss>"""
    found, method = extract_candidates(rss, "application/rss+xml", "https://jobs.example.com/feed")
    assert method == "feed"
    assert len(found) == 2
    assert found[0].external_id == "feed-9"
    assert found[0].url == "https://jobs.example.com/j/9"


def test_atom_feed_items() -> None:
    atom = b"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Data Engineer</title>
        <link href="https://jobs.example.com/j/77"/><id>atom-77</id></entry>
    </feed>"""
    found, method = extract_candidates(atom, "application/atom+xml", "https://x.example/feed")
    assert method == "feed"
    assert found[0].title == "Data Engineer"
    assert found[0].url == "https://jobs.example.com/j/77"


def test_html_anchor_fallback_filters_non_job_links() -> None:
    html = b"""
    <html><body>
      <a href="/about">About us</a>
      <a href="/careers/swe-1">Software Engineer - apply now</a>
      <a href="/careers/pm-2">Product Manager role</a>
      <a href="http://insecure.example.com/job/3">Junior role</a>
    </body></html>"""
    found, method = extract_candidates(html, "text/html", "https://jobs.example.com/")
    assert method == "html-anchors"
    urls = {job.url for job in found}
    assert "https://jobs.example.com/careers/swe-1" in urls
    assert "https://jobs.example.com/careers/pm-2" in urls
    assert all(url.startswith("https://") for url in urls)


def test_region_selector_limits_scope() -> None:
    html = b"""
    <html><body>
      <a href="/careers/outside-1">Outside role - apply</a>
      <div id="job-list">
        <a href="/careers/inside-1">Inside role - apply</a>
      </div>
    </body></html>"""
    found, _ = extract_candidates(
        html, "text/html", "https://jobs.example.com/", region_selector="job-list"
    )
    assert [job.url for job in found] == ["https://jobs.example.com/careers/inside-1"]


def test_candidates_bounded() -> None:
    links = b"".join(
        f'<a href="/careers/j{i}">Role {i} - job</a>'.encode() for i in range(MAX_CANDIDATES + 50)
    )
    html = b"<html><body>" + links + b"</body></html>"
    found, _ = extract_candidates(html, "text/html", "https://jobs.example.com/")
    assert len(found) == MAX_CANDIDATES


def test_unparseable_content_returns_empty() -> None:
    found, method = extract_candidates(b"\x00\x01binary", "application/octet-stream", "https://x.example/")
    assert found == []
    assert method == "html-anchors"


def test_malformed_jsonld_falls_back_to_anchors() -> None:
    html = b"""
    <script type="application/ld+json">{"@type":"JobPosting",broken</script>
    <a href="/careers/j1">Real role - apply</a>"""
    found, method = extract_candidates(html, "text/html", "https://jobs.example.com/")
    assert method == "html-anchors"
    assert found[0].title.startswith("Real role")


def test_relative_job_urls_resolved() -> None:
    html = b'<a href="jobs/rel-1">Analyst - job opening</a>'
    found, _ = extract_candidates(html, "text/html", "https://jobs.example.com/careers/")
    assert found[0].url == "https://jobs.example.com/careers/jobs/rel-1"

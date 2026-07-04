"""Job-posting scraping via Playwright (headless Chromium).

Fetch and extraction are split so extraction is a pure, fixture-testable function:

  scrape(url) = fetch_html(url)  # Playwright, network
              + extract(html, url)  # pure parsing, no network

Extraction leans on schema.org JSON-LD ``JobPosting`` (server-rendered by Greenhouse,
Lever, LinkedIn public pages, justjoin.it, nofluffjobs, ...) with a ``<meta>``/``<title>``
fallback. Per-board CSS selectors are deferred. See dev/25_06_minimal_req.md (Scraping).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# Domain suffix -> board slug. Matched against the registrable host (leading "www." stripped).
_BOARD_DOMAINS = {
    "linkedin.com": "linkedin",
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "justjoin.it": "justjoin",
    "nofluffjobs.com": "nofluffjobs",
    "pracuj.pl": "pracuj",
}


@dataclass
class ScrapedJob:
    title: str
    company: str
    location: str
    description: str
    raw_html: str
    source_board: str


def detect_board(url: str) -> str:
    """Map a posting URL's host to a known board slug, or ``"generic"``."""
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for domain, slug in _BOARD_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return slug
    return "generic"


def fetch_html(url: str) -> str:
    """Fetch a page's rendered HTML with headless Chromium.

    The only network/Playwright code in this module. Uses the sync API, which is correct
    for Django's sync views but **blocks the web worker** for the duration of the load —
    move scrapes to a management command or a queue for anything latency-sensitive
    (deferred; see the plan's follow-ups).
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return page.content()
        finally:
            browser.close()


def _text(value) -> str:
    """Collapse an HTML-or-plain string to trimmed plain text."""
    if not value:
        return ""
    return BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)


def _iter_jsonld_nodes(soup: BeautifulSoup):
    """Yield every JSON-LD object on the page, flattening ``@graph`` and list forms."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue  # malformed block — skip, don't fail the whole extraction
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                if "@graph" in node:
                    stack.extend(
                        node["@graph"]
                        if isinstance(node["@graph"], list)
                        else [node["@graph"]]
                    )
                yield node


def _is_job_posting(node: dict) -> bool:
    node_type = node.get("@type", "")
    if isinstance(node_type, list):
        return "JobPosting" in node_type
    return node_type == "JobPosting"


def _jsonld_location(job: dict) -> str:
    loc = job.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if not isinstance(loc, dict):
        return ""
    address = loc.get("address")
    if isinstance(address, str):
        return address.strip()
    if isinstance(address, dict):
        return (address.get("addressLocality") or address.get("addressRegion") or "").strip()
    return ""


def _meta(soup: BeautifulSoup, *, prop: str = "", name: str = "") -> str:
    if prop:
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            return tag["content"].strip()
    if name:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def extract(html: str, url: str) -> ScrapedJob:
    """Parse a fetched page into a ``ScrapedJob`` (pure — no network)."""
    soup = BeautifulSoup(html, "html.parser")

    title = company = location = description = ""

    # 1. JSON-LD JobPosting (most robust; server-rendered by most boards).
    for node in _iter_jsonld_nodes(soup):
        if not _is_job_posting(node):
            continue
        title = title or (node.get("title") or "").strip()
        org = node.get("hiringOrganization")
        if not company:
            if isinstance(org, dict):
                company = (org.get("name") or "").strip()
            elif isinstance(org, str):
                company = org.strip()
        location = location or _jsonld_location(node)
        description = description or _text(node.get("description"))

    # 2. Meta / <title> fallback for anything still missing.
    if not title:
        title = _meta(soup, prop="og:title") or (
            soup.title.get_text(strip=True) if soup.title else ""
        )
    if not description:
        description = _meta(soup, name="description") or _meta(soup, prop="og:description")

    return ScrapedJob(
        title=title,
        company=company,
        location=location,
        description=description,
        raw_html=html,
        source_board=detect_board(url),
    )


def scrape(url: str) -> ScrapedJob:
    """Fetch ``url`` with Chromium and extract its job fields."""
    return extract(fetch_html(url), url)

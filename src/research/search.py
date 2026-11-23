"""Find candidate documentation URLs for one application.

Search snippets are clues only. Callers must open a page before treating
anything on it as evidence.
"""

import time
from urllib.parse import urlparse

from ddgs import DDGS
from ddgs.exceptions import DDGSException, TimeoutException

# Parent companies host many products. A hit on these domains is official
# only when it matches this app's own site or documentation hint.
SHARED_PARENT_DOMAINS = {
    "adobe.com",
    "amazon.com",
    "atlassian.com",
    "facebook.com",
    "google.com",
    "intuit.com",
    "meta.com",
    "microsoft.com",
    "salesforce.com",
    "zoho.com",
}


def host_of(url):
    if not url:
        return ""
    host = urlparse(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def parent_domain(host):
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def same_site(url, reference_url):
    """True when url is the reference host or a subdomain of it."""
    host = host_of(url)
    reference = host_of(reference_url)
    if not host or not reference:
        return False
    return host == reference or host.endswith("." + reference)


def is_official_url(url, app):
    """Identify vendor-controlled official sources, excluding community forums."""

    host = host_of(url)
    website = app.get("website") or ""
    hint = app.get("documentation_hint") or ""

    if not host:
        return False

    excluded = (
        "community.",
        "forums.",
        "forum.",
        "discussions.",
        "ideas.",
    )

    if host.startswith(excluded):
        return False

    # Documentation domain is trusted.
    if hint and same_site(url, hint):
        return True

    site_host = host_of(website)

    if not site_host or not same_site(url, website):
        return False

    if parent_domain(site_host) in SHARED_PARENT_DOMAINS:
        return host == site_host

    return True


def _result_url(item):
    return item.get("href") or item.get("url") or ""


def search_queries(app):
    name = app.get("name", "")
    return [
        f"{name} official API documentation",
        f"{name} developer documentation authentication",
        f"{name} Model Context Protocol MCP server",
    ]


def search_documentation(app, max_results=5, timeout=20):
    """Return structured search hits. Empty results are a handled failure."""
    queries = search_queries(app)
    found = []
    errors = []
    seen = set()

    try:
        searcher = DDGS(timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - report setup failures, do not crash the pipeline
        return {"queries": queries, "results": [], "errors": [f"Search setup failed: {exc}"]}

    for query in queries:
        hits = None
        query_error = None
        for attempt in range(2):
            try:
                hits = searcher.text(query, max_results=max_results)
                query_error = None
                break
            except TimeoutException as exc:
                query_error = f"Search timed out for {query!r}: {exc}"
            except DDGSException as exc:
                query_error = f"Search failed for {query!r}: {exc}"
            except Exception as exc:  # noqa: BLE001
                query_error = f"Search failed for {query!r}: {exc}"
            if attempt == 0:
                time.sleep(1)
        if query_error:
            errors.append(query_error)
            continue

        for item in hits or []:
            url = _result_url(item)
            if not url or url in seen:
                continue
            seen.add(url)
            found.append(
                {
                    "query": query,
                    "title": item.get("title") or "",
                    "url": url,
                    "official": is_official_url(url, app),
                }
            )

    found.sort(
    key=lambda item: (
        not item["official"],
        "developer" not in item["url"].lower()
        and "docs" not in item["url"].lower()
        and "api" not in item["url"].lower(),
        "mcp" not in item["url"].lower(),
    )
)
    return {"queries": queries, "results": found, "errors": errors}

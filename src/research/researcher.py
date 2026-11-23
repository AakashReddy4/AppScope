"""Research one application from pages we actually fetch.

A search snippet is not evidence. A Composio catalogue row is not evidence
that the vendor API is free to use. Unknown stays unknown.
"""

import re
import time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from src.research.search import is_official_url, same_site

AUTH_PATTERNS = (
    ("OAuth2", re.compile(r"\boauth\s*2(?:\.0)?\b|\boauth2\b", re.I)),
    ("API key", re.compile(r"\bapi[\s-]?keys?\b", re.I)),
    ("Access token", re.compile(r"\baccess tokens?\b|\bprivate app tokens?\b", re.I)),
    ("Basic authentication", re.compile(r"\bbasic authentication\b|\bhttp basic\b|\bbasic auth\b", re.I)),
    ("Bearer/token authentication", re.compile(r"\bbearer tokens?\b|\bbearer authentication\b", re.I)),
)
OTHER_AUTH_PATTERNS = (
    ("SAML", re.compile(r"\bSAML\b")),
    ("JWT", re.compile(r"\bJWT\b")),
    ("HMAC", re.compile(r"\bHMAC\b")),
)
ACCESS_RULES = (
    (
        "Paid plan required",
        re.compile(
            r"paid plan|requires a paid|subscription required|"
            r"enterprise plan required|paid subscription|"
            r"billing plan required",
            re.I,
        ),
    ),
    (
        "Admin approval required",
        re.compile(
            r"admin approval|requires approval|approval required|"
            r"administrator must approve|approved by an admin",
            re.I,
        ),
    ),
    (
        "Partnership/contact-sales required",
        re.compile(
            r"contact sales|contact our sales|partnership required|"
            r"sales team|commercial agreement required",
            re.I,
        ),
    ),
    (
        "Free developer access",
        re.compile(
            r"free developer|developer account is free|"
            r"free api key|free developer account|"
            r"free developer program",
            re.I,
        ),
    ),
    (
        "Free trial",
        re.compile(r"free trial|trial period", re.I),
    ),
    (
        "Self-serve",
        re.compile(
            r"self-serve|self serve|"
            r"create (?:an? )?api key|generate (?:an? )?api key|"
            r"create (?:an? )?access token|"
            r"generate (?:an? )?access token|"
            r"manage api keys in|"
            r"api keys? (?:can be )?created in",
            re.I,
        ),
    ),
)
API_PATTERNS = (
    ("REST", re.compile(r"\bREST(?:ful)?\b", re.I)),
    ("GraphQL", re.compile(r"\bGraphQL\b", re.I)),
)
OTHER_API_PATTERNS = (
    ("SOAP", re.compile(r"\bSOAP\b")),
    ("gRPC", re.compile(r"\bgRPC\b")),
    ("WebSocket", re.compile(r"\bWebSockets?\b", re.I)),
)
NO_PUBLIC_API = re.compile(r"no public api|does not (?:offer|provide|have) a public api|api is not available", re.I)
MCP_PATTERN = re.compile(r"model context protocol|\bmcp server\b", re.I)


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def fetch_page(url, max_bytes=400_000):
    """Fetch a webpage and return decoded HTML text."""

    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "identity",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=25,
            allow_redirects=True,
        )

        response.raise_for_status()

        # requests handles response decoding; do not use response.raw.read().
        text = response.text[:max_bytes]

        return {
            "url": response.url,
            "ok": True,
            "error": "",
            "text": text,
            "html": text,
        }

    except requests.RequestException as exc:
        return {
            "url": url,
            "ok": False,
            "error": str(exc),
            "text": "",
            "html": "",
        }


def html_to_text(html):
    without_scripts = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", without_scripts)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def meta_description(html):
    patterns = (
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            text = unescape(re.sub(r"\s+", " ", match.group(1))).strip()
            if text:
                return text[:400]
    return ""


def same_host_links(page_url, html):
    links = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
        absolute = urljoin(page_url, href)
        if not same_site(absolute, page_url):
            continue
        lowered = absolute.lower()
        if any(token in lowered for token in ("/api", "graphql", "/rest", "reference", "auth")):
            links.append(absolute.split("#")[0])
    unique = []
    for link in links:
        if link not in unique:
            unique.append(link)
    return unique[:5]


def _matched_labels(text, patterns):
    return [label for label, pattern in patterns if pattern.search(text)]

def _detect_api_types(text):
    """Detect API technologies only when mentioned in API context."""

    patterns = (
        ("REST", re.compile(r"\bREST(?:ful)?\b", re.I)),
        ("GraphQL", re.compile(r"\bGraphQL\b", re.I)),
        ("SOAP", re.compile(r"\bSOAP\b", re.I)),
        ("gRPC", re.compile(r"\bgRPC\b", re.I)),
        ("WebSocket", re.compile(r"\bWebSockets?\b", re.I)),
    )

    api_context = re.compile(
        r"\bapi\b|\bendpoint\b|\bgraphql\b|"
        r"\bwebhook\b|\bdeveloper\b",
        re.I,
    )

    detected = []

    for label, pattern in patterns:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 150)
            end = min(len(text), match.end() + 150)

            if api_context.search(text[start:end]):
                detected.append(label)
                break

    return detected


def _access_in_context(text):
    """Accept an access phrase only when it sits near API or developer wording."""
    labels = []
    for label, pattern in ACCESS_RULES:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 300)
            end = min(len(text), match.end() + 300)
            if re.search(r"\bapi\b|\bdeveloper\b", text[start:end], re.I):
                labels.append(label)
                break
    return labels


def _coverage_note(coverage):
    status = (coverage or {}).get("match_status")
    if status == "confirmed_match":
        return (
            "Composio catalogue has a confirmed toolkit. "
            "That does not prove the vendor API is free or self-serve."
        )
    if status == "no_match":
        return (
            "No confirmed Composio toolkit match. "
            "That does not prove the application is unsupported."
        )
    if status:
        return "Composio match is not confirmed, so it is not counted as coverage."
    return "No Composio coverage row was available for this application."


def _compose_mcp(official_pages, community_pages, coverage, app_name):
    labels = []
    url = ""
    notes = []
    name = (app_name or "").lower()
    for page in official_pages:
        if page["ok"] and name and name in page["text"].lower() and MCP_PATTERN.search(page["text"]):
            labels.append("Official MCP server")
            url = url or page["url"]
            break
    for page in community_pages:
        if page["ok"] and name and name in page["text"].lower() and MCP_PATTERN.search(page["text"]):
            labels.append("Community MCP server")
            url = url or page["url"]
            break
    if (coverage or {}).get("match_status") == "confirmed_match":
        labels.append("Composio toolkit")
        notes.append("Composio toolkit comes from the catalogue match, not from vendor documentation.")

    official_read = any(page["ok"] for page in official_pages)
    if official_read and "Official MCP server" not in labels and "Community MCP server" not in labels:
        labels.append("No verified MCP found")
    if not labels:
        labels.append("Unknown")
    return labels, url, notes


def _buildability(api_types, access_values, blocked):
    """Classify buildability without treating missing access evidence as proof."""

    if blocked:
        return "Blocked", "Fetched official text explicitly says a public API is not available."

    if not api_types:
        return "Unknown", "No API surface was verified on a fetched official page."

    gated = {
        "Paid plan required",
        "Admin approval required",
        "Partnership/contact-sales required",
    }

    open_access = {
        "Self-serve",
        "Free developer access",
        "Free trial",
    }

    if access_values & gated and access_values & open_access:
        return (
            "Moderate",
            "API documentation exists, but access requirements vary or conflict. "
            "The exact access conditions need verification.",
        )

    if access_values & gated:
        return (
            "Difficult",
            "Official documentation indicates paid access, approval, or partnership requirements.",
        )

    if access_values & open_access:
        return (
            "Easy",
            "Official documentation indicates self-serve, free developer, or trial access.",
        )

    return (
        "Moderate",
        "An API surface was detected, but access requirements could not be established. "
        "API availability is not proof of self-serve access.",
    )


def _blockers(access_values, blocked):
    blockers = []
    if "Paid plan required" in access_values:
        blockers.append("Paid access")
    if "Admin approval required" in access_values:
        blockers.append("Approval requirements")
    if "Partnership/contact-sales required" in access_values:
        blockers.append("Partnership requirements")
    if blocked:
        blockers.append("Restricted API")
    return blockers


def research_app(app, coverage=None, search_result=None, fetch=fetch_page):
    """Build one research record. Unverified fields stay unknown."""
    if search_result is None:
        from src.research.search import search_documentation

        search_result = search_documentation(app)

    pages = []
    errors = list(search_result.get("errors") or [])
    hint = (app.get("documentation_hint") or "").strip()
    candidate_urls = []
    if hint:
        candidate_urls.append(hint)
    for hit in search_result.get("results") or []:
        if hit.get("official") and hit.get("url") not in candidate_urls:
            candidate_urls.append(hit["url"])

    for url in candidate_urls[:5]:
        page = fetch(url)
        pages.append(page)
        if not page["ok"]:
            errors.append(f"Could not fetch {url}: {page['error']}")

    official_pages = [
        page for page in pages
        if page["ok"] and is_official_url(page["url"], app)
    ]

    if official_pages:
        extra_links = same_host_links(
            official_pages[0]["url"],
            official_pages[0]["html"],
        )

        extra_pages_fetched = 0

        for link in extra_links:
            if any(page["url"] == link for page in pages):
                continue

            if extra_pages_fetched >= 5:
                break

            page = fetch(link)
            pages.append(page)
            extra_pages_fetched += 1

            if page["ok"] and is_official_url(page["url"], app):
                official_pages.append(page)
            elif not page["ok"]:
                errors.append(
                    f"Could not fetch {link}: {page['error']}"
                )

    community_pages = []

    for hit in search_result.get("results") or []:
        url = hit.get("url") or ""
        title = (hit.get("title") or "").lower()

        if "mcp" not in url.lower() and "mcp" not in title and "model context protocol" not in title:
            continue

        if is_official_url(url, app):
            continue

        page = fetch(url)
        community_pages.append(page)
        pages.append(page)

        if not page["ok"]:
            errors.append(f"Could not fetch {url}: {page['error']}")

        break

    official_text = "\n".join(page["text"] for page in official_pages)

    auth_methods = _matched_labels(official_text, AUTH_PATTERNS) if official_text else []
    other_auth = _matched_labels(official_text, OTHER_AUTH_PATTERNS) if official_text else []

    if other_auth:
        auth_methods.append("Other")

    if not auth_methods:
        auth_methods = ["Unknown"]

    access_values = set(_access_in_context(official_text)) if official_text else set()
    access_list = sorted(access_values) if access_values else ["Unknown"]

    api_types = _detect_api_types(official_text) if official_text else []

    other_api = [
        item for item in api_types
        if item in {"SOAP", "gRPC", "WebSocket"}
    ]

    if other_api:
        api_types = [
            item for item in api_types
            if item not in {"SOAP", "gRPC", "WebSocket"}
        ]
        api_types.append("Other")

    blocked = bool(official_text and NO_PUBLIC_API.search(official_text))

    if not api_types:
        api_types = ["Unknown"]
        api_explanation = "No REST, GraphQL, or other API type was verified on a fetched official page."
    else:
        details = [item for item in api_types if item != "Other"]

        if other_api:
            details.append(", ".join(other_api))

        api_explanation = "Fetched official documentation mentions " + ", ".join(details) + "."

    description = ""
    description_status = "unknown"
    for page in official_pages:
        description = meta_description(page["html"])
        if description:
            description_status = "verified"
            break

    mcp_labels, mcp_url, mcp_notes = _compose_mcp(official_pages, community_pages, coverage, app.get("name", ""))
    buildability, buildability_reason = _buildability(
        [item for item in api_types if item != "Unknown"],
        access_values,
        blocked,
    )
    blockers = _blockers(access_values, blocked)

    doc_url = official_pages[0]["url"] if official_pages else ""
    api_url = ""

    for page in official_pages:
        lowered = page["url"].lower()
        if any(token in lowered for token in ("api", "graphql", "rest", "reference")):
            api_url = page["url"]
            break

    verified_fields = sum([
        auth_methods != ["Unknown"],
        access_list != ["Unknown"],
        api_types != ["Unknown"],
        description_status == "verified",
    ])

    if (
        official_pages
        and auth_methods != ["Unknown"]
        and access_list != ["Unknown"]
        and api_types != ["Unknown"]
        and description_status == "verified"
        and not errors
    ):
        confidence = "high"
    elif official_pages and (
        auth_methods != ["Unknown"] or api_types != ["Unknown"]
    ):
        confidence = "medium"
    else:
        confidence = "low"

    needs_review = []
    if auth_methods == ["Unknown"]:
        needs_review.append("authentication_methods")
    if access_list == ["Unknown"]:
        needs_review.append("access_model")
    if api_types == ["Unknown"]:
        needs_review.append("api_surface")
    if "Official MCP server" not in mcp_labels and "Community MCP server" not in mcp_labels:
        needs_review.append("mcp")
    if buildability == "Unknown":
        needs_review.append("buildability")
    if description_status != "verified":
        needs_review.append("description")

    evidence_notes = [
        "Only text from fetched pages was used as evidence.",
        "Search snippets were not treated as proof.",
        _coverage_note(coverage),
    ]
    if other_auth:
        evidence_notes.append("Other authentication phrases seen: " + ", ".join(other_auth) + ".")
    if other_api:
        evidence_notes.append("Other API phrases seen: " + ", ".join(other_api) + ".")
    evidence_notes.extend(mcp_notes)
    if errors:
        evidence_notes.append("Some searches or fetches failed. See research_errors.")

    return {
        "app_id": app["id"],
        "app_name": app["name"],
        "category": app.get("category", ""),
        "website": app.get("website", ""),
        "documentation_hint": hint,
        "status": "completed",
        "description": description if description_status == "verified" else "",
        "description_status": description_status,
        "authentication_methods": auth_methods,
        "authentication_notes": (
            "Other methods named on the fetched page: " + ", ".join(other_auth)
            if other_auth
            else ""
        ),
        "access_model": access_list,
        "api_surface": api_types,
        "api_explanation": api_explanation,
        "mcp_availability": mcp_labels,
        "buildability": buildability,
        "buildability_reason": buildability_reason,
        "blockers": blockers,
        "evidence": {
            "official_documentation_url": doc_url,
            "official_api_reference_url": api_url,
            "mcp_url": mcp_url,
            "notes": " ".join(evidence_notes),
            "confidence": confidence,
            "needs_human_verification": needs_review,
        },
        "composio_coverage": {
            "match_status": (coverage or {}).get("match_status", "not_in_coverage_file"),
            "matched_toolkit_name": (coverage or {}).get("matched_toolkit_name"),
            "matched_toolkit_slug": (coverage or {}).get("matched_toolkit_slug"),
            "tools_count": (coverage or {}).get("tools_count"),
            "catalogue_auth_schemes": (coverage or {}).get("auth_schemes"),
            "note": _coverage_note(coverage),
        },
        "pages_fetched": [page["url"] for page in pages if page["ok"]],
        "research_errors": errors,
        "researched_at": _now(),
    }

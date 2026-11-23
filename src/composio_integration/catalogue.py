"""Download the Composio toolkit catalogue.

Uses the installed SDK client, which calls GET /api/v3.1/toolkits.
Run from the project root:

    python -m src.composio_integration.catalogue
"""

import json
import os
import sys
from pathlib import Path

from composio import Composio
from composio.exceptions import ApiKeyNotProvidedError
from composio_client import (
    APIConnectionError,
    APIError,
    APIResponseValidationError,
    APIStatusError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT / "data" / "composio_catalogue_raw.json"
NORMALIZED_PATH = ROOT / "data" / "composio_catalogue.json"
ENDPOINT = "GET /api/v3.1/toolkits"
MAX_PAGES = 500


class CatalogueError(Exception):
    """The catalogue could not be retrieved or saved."""


def load_api_key() -> None:
    """Load COMPOSIO_API_KEY from the project .env without printing it."""
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    if not api_key:
        raise CatalogueError(
            "COMPOSIO_API_KEY is missing. Add it to the .env file in the "
            "project root, then run this command again."
        )


def page_to_dict(page: object) -> dict:
    """Turn one SDK page into plain JSON, keeping only fields the API returned."""
    dump = getattr(page, "model_dump", None)
    if not callable(dump):
        raise CatalogueError(
            "The toolkit catalogue response was not the documented SDK model. "
            "Expected a page with items and next_cursor."
        )
    data = dump(mode="json", by_alias=True)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise CatalogueError(
            "The toolkit catalogue response did not contain an items list."
        )
    next_cursor = data.get("next_cursor")
    if next_cursor is not None and not isinstance(next_cursor, str):
        raise CatalogueError(
            "The toolkit catalogue response included a next_cursor that was not text."
        )
    return data


def normalize_toolkit(item: object) -> dict:
    """Keep the useful fields that this toolkit object actually contains."""
    if hasattr(item, "model_dump"):
        data = item.model_dump(mode="json")
    elif isinstance(item, dict):
        data = item
    else:
        raise CatalogueError(
            "A toolkit record was not an object, so it could not be saved."
        )

    record = {}
    for field in ("name", "slug"):
        if field in data:
            record[field] = data[field]

    meta = data.get("meta")
    if isinstance(meta, dict):
        if "description" in meta:
            record["description"] = meta["description"]
        if "categories" in meta:
            record["categories"] = meta["categories"]
        if "tools_count" in meta:
            record["tools_count"] = meta["tools_count"]

    authentication = {}
    for field in (
        "auth_schemes",
        "composio_managed_auth_schemes",
        "no_auth",
        "auth_guide_url",
    ):
        if field in data and data[field] is not None:
            authentication[field] = data[field]
    if authentication:
        record["authentication"] = authentication
    return record


def fetch_pages(composio) -> list[dict]:
    """Follow next_cursor until the API says there is no further page."""
    pages = []
    cursor = None
    seen_cursors = set()

    while True:
        if len(pages) >= MAX_PAGES:
            raise CatalogueError(
                "Pagination stopped after 500 pages because next_cursor did not end."
            )

        page = composio.toolkits.list(cursor=cursor)
        data = page_to_dict(page)
        pages.append(data)

        next_cursor = data.get("next_cursor") or None
        if next_cursor is None:
            return pages
        if next_cursor in seen_cursors:
            raise CatalogueError(
                "Pagination stopped because the API repeated a next_cursor."
            )
        seen_cursors.add(next_cursor)
        cursor = next_cursor


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def explain_sdk_error(exc: Exception) -> str:
    """Describe an SDK failure without including request headers or the API key."""
    message = getattr(exc, "message", None) or str(exc)
    status_code = getattr(exc, "status_code", None)

    if isinstance(exc, RateLimitError):
        return (
            "Composio rate-limited the toolkit catalogue request "
            f"(HTTP {status_code}). Wait and run the command again. {message}"
        )
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return (
            "Composio rejected COMPOSIO_API_KEY "
            f"(HTTP {status_code}). Check the project key in .env. {message}"
        )
    if isinstance(exc, APIResponseValidationError):
        return (
            "Composio returned a toolkit catalogue body the installed SDK "
            f"could not read. {message}"
        )
    if isinstance(exc, APIStatusError):
        return (
            "Composio returned an unexpected HTTP status "
            f"({status_code}) for the toolkit catalogue. {message}"
        )
    if isinstance(exc, APIConnectionError):
        return f"Could not reach the Composio API. {message}"
    return message


def main() -> None:
    try:
        load_api_key()
        composio = Composio()
        pages = fetch_pages(composio)
    except CatalogueError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    except ApiKeyNotProvidedError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    except APIError as exc:
        raise SystemExit(f"Error: {explain_sdk_error(exc)}") from exc

    toolkits = []
    for page in pages:
        for item in page["items"]:
            toolkits.append(normalize_toolkit(item))

    write_json(RAW_PATH, {"endpoint": ENDPOINT, "pages": pages})
    write_json(NORMALIZED_PATH, toolkits)

    slugs = [toolkit["slug"] for toolkit in toolkits if "slug" in toolkit]
    print(f"Total toolkit records retrieved: {len(toolkits)}")
    print(f"Unique toolkit slugs: {len(set(slugs))}")
    print("First 10 toolkits:")
    for toolkit in toolkits[:10]:
        name = toolkit.get("name", "(no name)")
        slug = toolkit.get("slug", "(no slug)")
        print(f"- {name} ({slug})")
    print(f"Raw response: {RAW_PATH}")
    print(f"Normalized catalogue: {NORMALIZED_PATH}")


if __name__ == "__main__":
    try:
        main()
    except CatalogueError as exc:
        sys.exit(f"Error: {exc}")

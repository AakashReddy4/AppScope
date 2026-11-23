"""Research every application, saving progress after each one.

    python -m src.research.pipeline
    python -m src.research.pipeline --limit 2
    python -m src.research.pipeline --app Salesforce
    python -m src.research.pipeline --force
"""

import argparse
import csv
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from src.research.researcher import research_app

ROOT = Path(__file__).resolve().parents[2]
APPS_PATH = ROOT / "data" / "apps.json"
COVERAGE_PATH = ROOT / "data" / "composio_coverage.json"
RESULTS_PATH = ROOT / "data" / "research_results.json"
CSV_PATH = ROOT / "data" / "research_results.csv"
PROGRESS_PATH = ROOT / "data" / "research_progress.json"
FAILURES_PATH = ROOT / "data" / "research_failures.json"

CSV_FIELDS = [
    "app_id",
    "app_name",
    "category",
    "status",
    "description",
    "description_status",
    "authentication_methods",
    "access_model",
    "api_surface",
    "api_explanation",
    "mcp_availability",
    "buildability",
    "blockers",
    "official_documentation_url",
    "official_api_reference_url",
    "mcp_url",
    "confidence",
    "needs_human_verification",
    "composio_match_status",
    "research_errors",
]


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def joined(value):
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return "" if value is None else str(value)


def to_csv_row(result):
    evidence = result.get("evidence") or {}
    coverage = result.get("composio_coverage") or {}
    return {
        "app_id": result.get("app_id"),
        "app_name": result.get("app_name"),
        "category": result.get("category"),
        "status": result.get("status"),
        "description": result.get("description"),
        "description_status": result.get("description_status"),
        "authentication_methods": joined(result.get("authentication_methods")),
        "access_model": joined(result.get("access_model")),
        "api_surface": joined(result.get("api_surface")),
        "api_explanation": result.get("api_explanation"),
        "mcp_availability": joined(result.get("mcp_availability")),
        "buildability": result.get("buildability"),
        "blockers": joined(result.get("blockers")),
        "official_documentation_url": evidence.get("official_documentation_url"),
        "official_api_reference_url": evidence.get("official_api_reference_url"),
        "mcp_url": evidence.get("mcp_url"),
        "confidence": evidence.get("confidence"),
        "needs_human_verification": joined(evidence.get("needs_human_verification")),
        "composio_match_status": coverage.get("match_status"),
        "research_errors": joined(result.get("research_errors")),
    }


def write_outputs(results, failures):
    ordered = sorted(results, key=lambda item: item.get("app_id") or 0)
    write_json(RESULTS_PATH, ordered)
    write_json(FAILURES_PATH, failures)
    completed = [item["app_id"] for item in ordered if item.get("status") == "completed"]
    failed = [item["app_id"] for item in ordered if item.get("status") == "failed"]
    write_json(
        PROGRESS_PATH,
        {
            "completed_app_ids": completed,
            "failed_app_ids": failed,
            "completed_count": len(completed),
            "failed_count": len(failed),
            "updated_at": _now(),
        },
    )
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for result in ordered:
            writer.writerow(to_csv_row(result))


def validate_results(apps, results):
    """Check identity rules. Partial runs are valid; a full run must cover 100."""
    app_ids = [app["id"] for app in apps]
    result_ids = [item.get("app_id") for item in results]
    errors = []
    if len(app_ids) != 100 or len(set(app_ids)) != 100:
        errors.append("data/apps.json does not contain exactly 100 unique applications.")
    if len(result_ids) != len(set(result_ids)):
        errors.append("Research results contain a duplicate app ID.")
    unknown = sorted(set(result_ids) - set(app_ids))
    if unknown:
        errors.append(f"Research results include unknown app IDs: {unknown}")
    completed = [item for item in results if item.get("status") == "completed"]
    if len(completed) == 100:
        if sorted(item["app_id"] for item in completed) != sorted(app_ids):
            errors.append("Completed results do not represent each application once.")
    return errors


def select_apps(apps, app_argument, limit):
    selected = apps
    if app_argument:
        needle = app_argument.lower()
        selected = [
            app for app in apps
            if str(app.get("id")) == app_argument or app.get("name", "").lower() == needle
        ]
        if not selected:
            raise SystemExit(f"No application matched {app_argument!r}.")
    if limit is not None:
        selected = selected[:limit]
    return selected


def run(limit=None, app_argument=None, force=False, delay=1.5):
    apps = load_json(APPS_PATH, [])
    coverage_rows = load_json(COVERAGE_PATH, [])
    coverage_by_id = {row["app_id"]: row for row in coverage_rows}
    results = load_json(RESULTS_PATH, [])
    failures = [item for item in load_json(FAILURES_PATH, []) if isinstance(item, dict)]
    by_id = {item["app_id"]: item for item in results if "app_id" in item}

    for app in select_apps(apps, app_argument, limit):
        existing = by_id.get(app["id"])
        if existing and existing.get("status") == "completed" and not force:
            print(f"Skip {app['id']} {app['name']} (already completed)")
            continue

        print(f"Research {app['id']} {app['name']}")
        try:
            result = research_app(app, coverage_by_id.get(app["id"]))
        except Exception as exc:  # noqa: BLE001 - log and continue with the next app
            result = {
                "app_id": app["id"],
                "app_name": app["name"],
                "category": app.get("category", ""),
                "status": "failed",
                "authentication_methods": ["Unknown"],
                "access_model": ["Unknown"],
                "api_surface": ["Unknown"],
                "mcp_availability": ["Unknown"],
                "buildability": "Unknown",
                "blockers": [],
                "evidence": {
                    "official_documentation_url": "",
                    "official_api_reference_url": "",
                    "mcp_url": "",
                    "notes": "Research failed before a record could be completed.",
                    "confidence": "low",
                    "needs_human_verification": ["authentication_methods", "access_model", "api_surface", "mcp", "buildability"],
                },
                "research_errors": [str(exc)],
                "researched_at": _now(),
            }
            failures.append(
                {
                    "app_id": app["id"],
                    "app_name": app["name"],
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "at": _now(),
                }
            )
            print(f"Failed {app['id']} {app['name']}: {exc}")
        else:
            failures = [item for item in failures if item.get("app_id") != app["id"]]
            print(
                f"Completed {app['id']} {app['name']}: "
                f"confidence {result['evidence']['confidence']}, "
                f"buildability {result['buildability']}"
            )

        by_id[app["id"]] = result
        write_outputs(list(by_id.values()), failures)
        time.sleep(delay)

    current = list(by_id.values())
    problems = validate_results(apps, current)
    print(f"Results saved: {len(current)}")
    if problems:
        for problem in problems:
            print(f"Validation error: {problem}")
        return 1
    print("Validation passed for the results saved so far.")
    if len([item for item in current if item.get("status") == "completed"]) < 100:
        print("This is a partial run. Unknown fields are not confirmed facts.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Research AppScope applications.")
    parser.add_argument("--limit", type=int, help="Research only the first N selected applications.")
    parser.add_argument("--app", help="Research one application by id or exact name.")
    parser.add_argument("--force", action="store_true", help="Research again even when a completed result exists.")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds to wait after each application.")
    args = parser.parse_args()
    raise SystemExit(run(limit=args.limit, app_argument=args.app, force=args.force, delay=args.delay))


if __name__ == "__main__":
    main()

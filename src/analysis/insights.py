"""Summarise automated research findings and distinguish them from manual verification."""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "data" / "research_results.json"
COVERAGE_PATH = ROOT / "data" / "composio_coverage.json"
OUTPUT_PATH = ROOT / "data" / "insights.json"


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def count_labels(records, field, ignore):
    """Count agent-detected labels. Unknown values remain separate."""
    counts = Counter()
    unknown = 0

    for record in records:
        labels = [
            label for label in record.get(field) or []
            if label not in ignore
        ]
        if not labels:
            unknown += 1
            continue
        for label in labels:
            counts[label] += 1

    return {
        "detected_counts": dict(counts),
        "unknown_or_not_found": unknown,
    }


def assessed_buildability(record):
    """Reassess buildability using existing research evidence."""

    current = record.get("buildability")
    api_types = {
        item for item in record.get("api_surface") or []
        if item != "Unknown"
    }
    access_values = {
        item for item in record.get("access_model") or []
        if item != "Unknown"
    }
    blockers = set(record.get("blockers") or [])

    if current == "Blocked":
        return "Blocked"

    if not api_types:
        return "Unknown"

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
        return "Moderate"

    if access_values & gated:
        return "Difficult"

    if access_values & open_access:
        return "Easy"

    return "Moderate"


def category_comparison(records):
    comparison = {}

    for record in records:
        category = record.get("category") or "Uncategorised"
        bucket = comparison.setdefault(
            category,
            {
                "completed": 0,
                "agent_detected_api": Counter(),
                "agent_assessed_buildability": Counter(),
            },
        )

        bucket["completed"] += 1

        api_labels = [
            label for label in record.get("api_surface") or []
            if label != "Unknown"
        ]
        bucket["agent_detected_api"].update(api_labels)

        verdict = assessed_buildability(record)
        if verdict != "Unknown":
            bucket["agent_assessed_buildability"][verdict] += 1

    return {
        category: {
            "completed": bucket["completed"],
            "agent_detected_api": dict(bucket["agent_detected_api"]),
            "agent_assessed_buildability": dict(
                bucket["agent_assessed_buildability"]
            ),
        }
        for category, bucket in comparison.items()
    }


def composio_summary(coverage_rows):
    counts = Counter(row.get("match_status") for row in coverage_rows)
    total = len(coverage_rows)
    confirmed = counts.get("confirmed_match", 0)
    possible = counts.get("possible_match", 0)
    percentage = round((confirmed / total) * 100, 1) if total else None

    return {
        "source": "data/composio_coverage.json",
        "note": "Catalogue matching is separate from vendor API research. A match does not prove free API access or successful integration.",
        "total_applications": total,
        "confirmed_matches": confirmed,
        "possible_matches": possible,
        "no_matches": counts.get("no_match", 0),
        "confirmed_coverage_percentage": percentage,
    }


def build_insights():
    results = load_json(RESULTS_PATH, [])
    coverage = load_json(COVERAGE_PATH, [])

    completed = [
        item for item in results
        if item.get("status") == "completed"
    ]
    failed = [
        item for item in results
        if item.get("status") == "failed"
    ]

    buildability = Counter(
        assessed_buildability(item) for item in completed
        if assessed_buildability(item) != "Unknown"
    )
    unknown_buildability = sum(
        1 for item in completed
        if assessed_buildability(item) == "Unknown"
    )

    blockers = Counter(
        label
        for item in completed
        for label in (item.get("blockers") or [])
    )

    opportunities = [
        {
            "app_id": item["app_id"],
            "app_name": item["app_name"],
            "category": item["category"],
            "reason": item.get("buildability_reason", ""),
            "evidence_url": (
                item.get("evidence") or {}
            ).get("official_documentation_url", ""),
        }
        for item in completed
        if assessed_buildability(item) == "Easy"
    ]

    return {
        "generated_at": datetime.now(timezone.utc).replace(
            microsecond=0
        ).isoformat(),
        "scope": {
            "applications_in_assignment": 100,
            "research_records": len(results),
            "completed_records": len(completed),
            "failed_records": len(failed),
            "note": (
                "Counts represent automated detections and assessments "
                "from fetched documentation, not independently verified facts. "
                "Unknown means insufficient evidence was found."
            ),
        },
        "authentication": count_labels(
            completed, "authentication_methods", {"Unknown"}
        ),
        "access_model": count_labels(
            completed, "access_model", {"Unknown"}
        ),
        "api_surface": count_labels(
            completed, "api_surface", {"Unknown"}
        ),
        "buildability": {
            "agent_assessed_counts": dict(buildability),
            "unknown": unknown_buildability,
            "note": (
                "Easy requires detected self-serve or free access; "
                "Difficult requires detected gating; Moderate means an API "
                "was detected but access is unknown or mixed. These are "
                "preliminary agent assessments, not confirmed integration tests."
            ),
        },
        "blockers": {
            "detected_counts": dict(blockers),
            "note": "Automated blocker detections require manual confirmation.",
        },
        "categories": category_comparison(completed),
        "easy_integration_opportunities": opportunities,
        "composio_catalogue": composio_summary(coverage),
    }


def main():
    insights = build_insights()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(insights, indent=2),
        encoding="utf-8",
    )

    scope = insights["scope"]
    catalogue = insights["composio_catalogue"]

    print(f"Completed research records: {scope['completed_records']}")
    print(f"Failed research records: {scope['failed_records']}")
    print(
        "Agent-assessed buildability: "
        f"{insights['buildability']['agent_assessed_counts']}"
    )
    print(
        "Unknown buildability: "
        f"{insights['buildability']['unknown']}"
    )
    print(
        "Composio confirmed catalogue matches: "
        f"{catalogue['confirmed_matches']}/{catalogue['total_applications']} "
        f"({catalogue['confirmed_coverage_percentage']}%)"
    )
    print(f"Wrote {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""Record human checks and score only the fields a person reviewed.

    python -m src.verification.framework
    python -m src.verification.framework --app-id 1 --field authentication_methods --verdict verified --evidence-url https://example.com/docs --notes "Checked the auth page."

Accuracy is null until at least one field has been checked.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "data" / "research_results.json"
OUTPUT_PATH = ROOT / "data" / "verification_results.json"
VERDICTS = {"verified", "incorrect", "partially_correct"}


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_store():
    return {
        "checks": [],
        "accuracy": None,
        "note": "Accuracy is calculated only for fields a human has marked. It is not a claim about unchecked research.",
    }


def load_store():
    if not OUTPUT_PATH.exists():
        return empty_store()
    data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    data.setdefault("checks", [])
    return data


def original_finding(app_id, field):
    if not RESULTS_PATH.exists():
        return None
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    for result in results:
        if result.get("app_id") == app_id:
            if field in result:
                return result[field]
            evidence = result.get("evidence") or {}
            if field in evidence:
                return evidence[field]
            return None
    return None


def summarise(checks):
    """Score checked fields only. Partially correct counts as not fully correct."""
    if not checks:
        return None
    correct = sum(1 for check in checks if check.get("verdict") == "verified")
    return {
        "fields_checked": len(checks),
        "verified": correct,
        "incorrect": sum(1 for check in checks if check.get("verdict") == "incorrect"),
        "partially_correct": sum(1 for check in checks if check.get("verdict") == "partially_correct"),
        "accuracy_percentage": round((correct / len(checks)) * 100, 1),
        "basis": "Percentage of human-checked fields marked verified. Unchecked apps and fields are excluded.",
    }


def record_check(app_id, field, verdict, evidence_url, notes, corrected=None):
    if verdict not in VERDICTS:
        raise SystemExit(f"Verdict must be one of: {', '.join(sorted(VERDICTS))}.")
    store = load_store()
    store["checks"].append(
        {
            "app_id": app_id,
            "field": field,
            "verdict": verdict,
            "original_finding": original_finding(app_id, field),
            "corrected_finding": corrected,
            "evidence_url": evidence_url,
            "notes": notes,
            "checked_at": _now(),
        }
    )
    store["accuracy"] = summarise(store["checks"])
    store["note"] = empty_store()["note"]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
    return store


def main():
    parser = argparse.ArgumentParser(description="Record a human verification check.")
    parser.add_argument("--app-id", type=int)
    parser.add_argument("--field")
    parser.add_argument("--verdict", choices=sorted(VERDICTS))
    parser.add_argument("--evidence-url", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--corrected", default=None)
    args = parser.parse_args()

    if args.app_id is None:
        store = load_store()
        store["accuracy"] = summarise(store["checks"])
        OUTPUT_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
        print(f"Human checks recorded: {len(store['checks'])}")
        print(f"Accuracy: {store['accuracy']}")
        print(store["note"])
        return 0

    if not args.field or not args.verdict:
        raise SystemExit("Recording a check requires --field and --verdict.")
    store = record_check(args.app_id, args.field, args.verdict, args.evidence_url, args.notes, args.corrected)
    print(f"Recorded check for app {args.app_id} field {args.field}.")
    print(f"Accuracy: {store['accuracy']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]

APPS_FILE = ROOT / "data" / "apps.json"
CATALOGUE_FILE = ROOT / "data" / "composio_catalogue.json"

OUTPUT_FILE = ROOT / "data" / "composio_coverage.json"
SUMMARY_FILE = ROOT / "data" / "composio_coverage_summary.json"


# Only use aliases when the products are genuinely equivalent.
ALIASES = {
    "Lark (Larksuite)": ["lark"],
    "Magento (Adobe Commerce)": ["magento"],
    "Monday.com": ["monday"],
    "Zoho CRM": ["zohocrm"],
    "Zoho Cliq": ["zohocliq"],
    "Amazon Selling Partner": ["amazonspapi"],
    "Google Ads": ["googleads"],
    "Meta Ads": ["metaads"],
    "LinkedIn Ads": ["linkedinads"],
    "WhatsApp Business": ["whatsappbusiness"],
    "Salesforce Commerce Cloud": ["salesforcecommerce"],
}


def normalize(value):
    """Normalize names for conservative comparison."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_candidates(app, catalogue, slug_index):
    app_name = app["name"]
    keys = {normalize(app_name)}

    for alias in ALIASES.get(app_name, []):
        keys.add(normalize(alias))

    matches = []

    for key in keys:
        if key in slug_index:
            matches.extend(slug_index[key])

    # Remove duplicate toolkit records.
    unique = {item["slug"]: item for item in matches}

    return list(unique.values())


def main():
    apps = load_json(APPS_FILE)
    catalogue = load_json(CATALOGUE_FILE)

    slug_index = {}

    for toolkit in catalogue:
        slug = toolkit.get("slug", "")
        name = toolkit.get("name", "")

        for value in [slug, name]:
            key = normalize(value)

            if key:
                slug_index.setdefault(key, []).append(toolkit)

    results = []

    for app in apps:
        candidates = get_candidates(app, catalogue, slug_index)

        if len(candidates) == 1:
            toolkit = candidates[0]

            result = {
                "app_id": app["id"],
                "app_name": app["name"],
                "category": app["category"],
                "match_status": "confirmed_match",
                "matched_toolkit_name": toolkit.get("name"),
                "matched_toolkit_slug": toolkit.get("slug"),
                "toolkit_description": toolkit.get("description"),
                "toolkit_categories": toolkit.get("categories", []),
                "tools_count": toolkit.get("tools_count"),
                "auth_schemes": toolkit.get(
                    "authentication", {}
                ).get("auth_schemes", []),
                "composio_managed_auth_schemes": toolkit.get(
                    "authentication", {}
                ).get("composio_managed_auth_schemes", []),
                "no_auth": toolkit.get(
                    "authentication", {}
                ).get("no_auth"),
                "match_reason": "Exact normalized name or explicit alias match"
            }

        elif len(candidates) > 1:
            result = {
                "app_id": app["id"],
                "app_name": app["name"],
                "category": app["category"],
                "match_status": "possible_match",
                "candidates": [
                    {
                        "name": item.get("name"),
                        "slug": item.get("slug")
                    }
                    for item in candidates
                ],
                "match_reason": "Multiple possible catalogue matches; manual review required"
            }

        else:
            result = {
                "app_id": app["id"],
                "app_name": app["name"],
                "category": app["category"],
                "match_status": "no_match",
                "matched_toolkit_name": None,
                "matched_toolkit_slug": None,
                "match_reason": "No exact or explicitly defined alias match found"
            }

        results.append(result)

    counts = Counter(item["match_status"] for item in results)

    summary = {
        "total_applications": len(apps),
        "total_catalogue_toolkits": len(catalogue),
        "confirmed_matches": counts["confirmed_match"],
        "possible_matches": counts["possible_match"],
        "no_matches": counts["no_match"],
        "coverage_percentage": round(
            counts["confirmed_match"] / len(apps) * 100, 2
        ) if apps else 0
    }

    assert len(results) == 100
    assert len({item["app_id"] for item in results}) == 100

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    with open(SUMMARY_FILE, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print("\nAPP SCOPE — COMPOSIO COVERAGE")
    print("-" * 40)

    for key, value in summary.items():
        print(f"{key}: {value}")

    print("\nAPPLICATION MATCH RESULTS")
    print("-" * 40)

    for item in results:
        print(
            f'{item["app_name"]}: {item["match_status"]}'
        )

    print("\nValidation successful.")
    print(f"Saved: {OUTPUT_FILE}")
    print(f"Saved: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
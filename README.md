# AppScope — AI Integration Intelligence

Take-home project for the AI Product Operations Intern role at Composio.

AppScope researches 100 applications and keeps two separate records:

- Composio toolkit coverage, from the installed Composio SDK catalogue
- Independent API research, from official pages the pipeline fetches

A Composio match does not prove that an API is free to use. No Composio match does not prove that an application is unsupported. A gated API is a finding, not a failed integration.

## Architecture

```
data/apps.json                         100 applications
src/composio_integration/catalogue.py  download the toolkit catalogue
src/composio_integration/matcher.py    conservative name and alias matching
src/research/search.py                 find documentation URLs
src/research/researcher.py             fetch pages and extract only verified facts
src/research/pipeline.py               resume, retries, and per-app saves
src/analysis/insights.py               distributions that keep unknown separate
src/verification/framework.py          human checks and accuracy for checked fields only
```

Python 3.11 through 3.15 is required by the Composio SDK. This environment uses Python 3.13. The package name is `composio`, not the legacy `composio-core` package.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put the Composio project API key in `.env` as `COMPOSIO_API_KEY`. `.env` and `.venv` are listed in `.gitignore`. The research pipeline does not read or print that key.

## Composio catalogue

```bash
python -m src.composio_integration.catalogue
python -m src.composio_integration.matcher
```

`catalogue.py` calls `GET /api/v3.1/toolkits` through the SDK and follows `next_cursor`. `matcher.py` writes confirmed matches separately from possible matches.

## Research pipeline

Search uses the `ddgs` package to discover URLs. A snippet is not evidence. The researcher fetches the documentation hint and official-domain hits, then looks for explicit authentication, access, API, and MCP wording. If a fact is not on a fetched page, the field stays `Unknown` and is listed for human verification.

```bash
python -m src.research.pipeline --limit 2
python -m src.research.pipeline --app Salesforce
python -m src.research.pipeline
python -m src.research.pipeline --force
```

The pipeline saves after every application. A completed result is skipped on the next run unless `--force` is set. A failed application is recorded in `data/research_failures.json` and retried on the next run. `--delay` defaults to 1.5 seconds between applications.

## Insights and verification

```bash
python -m src.analysis.insights
python -m src.verification.framework
```

Insights count verified labels only. Unknown values are reported separately. Composio coverage is read from `data/composio_coverage.json` and is not mixed into the API distributions.

To record a human check:

```bash
python -m src.verification.framework --app-id 1 --field authentication_methods --verdict verified --evidence-url https://developer.salesforce.com/ --notes "Checked the official auth docs."
```

Verdicts are `verified`, `incorrect`, or `partially_correct`. Accuracy is the share of checked fields marked `verified`. Unchecked fields are not included, and the project does not claim an accuracy percentage before those checks exist.

## Limitations

- The pipeline does not call a paid LLM and does not invent missing facts.
- Official pages can mention more than one product. Shared company domains are not treated as a match for a different product.
- Buildability stays `Unknown` when the API type or the access model was not verified.
- No blocker is recorded only because credentials were unavailable.
- The case-study page is not built yet.

## Current data

| File | Role |
| --- | --- |
| `data/apps.json` | 100 assignment applications |
| `data/composio_catalogue.json` | Normalised toolkit catalogue |
| `data/composio_catalogue_raw.json` | Raw catalogue pages |
| `data/composio_coverage.json` | Per-app catalogue match |
| `data/composio_coverage_summary.json` | Catalogue coverage totals |
| `data/research_results.json` | API research records |
| `data/research_results.csv` | Flat view of those records |
| `data/research_progress.json` | Completed and failed IDs |
| `data/research_failures.json` | Exceptions that did not stop the run |
| `data/insights.json` | Aggregate research summary |
| `data/verification_results.json` | Human checks |

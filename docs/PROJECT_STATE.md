# Project state

Updated after the research pipeline was added.

## Environment

- Python 3.13
- Virtual environment: `.venv`
- Composio Python SDK 0.34.0
- Search package: `ddgs`
- `COMPOSIO_API_KEY` belongs in `.env` and is gitignored

## Data already produced

- `data/apps.json`: 100 applications, 10 categories, 10 applications each
- `data/composio_catalogue.json`: 1,842 normalised toolkit records
- `data/composio_catalogue_raw.json`: raw catalogue responses
- `data/composio_coverage.json`: 71 confirmed matches, 29 no match
- Confirmed catalogue coverage: 71%

Possible matches are not counted as confirmed coverage. Catalogue auth schemes are stored beside the match and are not copied into the independent API research fields.

## Research pipeline

Implemented:

- `src/research/search.py`
- `src/research/researcher.py`
- `src/research/pipeline.py`
- `src/analysis/insights.py`
- `src/verification/framework.py`

The full 100-application research run is resumable and had not been finished when this note was written. Partial results, if present, are not a completed study.

## Not built

- Case-study frontend in `web/`
- Human verification of the research fields, until checks are recorded

## Do not overwrite

- `data/apps.json`
- `data/composio_catalogue.json`
- `data/composio_catalogue_raw.json`
- `data/composio_coverage.json`
- `data/composio_coverage_summary.json`

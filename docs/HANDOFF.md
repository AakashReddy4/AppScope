# Handoff

## What works

The Composio catalogue download and the conservative matcher already ran. Leave their output files in place and do not regenerate them unless the catalogue itself needs a refresh.

The research pipeline can start, stop, and continue. It writes `data/research_results.json`, `data/research_results.csv`, `data/research_progress.json`, and `data/research_failures.json` after each application.

## Run the rest of the research

From `D:\AppScope` with the virtual environment active:

```bash
.venv\Scripts\python.exe -m src.research.pipeline
.venv\Scripts\python.exe -m src.analysis.insights
```

Use `--limit 2` for a short test. Use `--app "Zoho CRM"` for one application. Use `--force` only when a completed record should be replaced.

A completed application is skipped. A record with status `failed` is tried again. Search and fetch errors that still produce a completed record are stored in `research_errors` and are not automatic retries.

## How to read a result

Trust a field only when it is not `Unknown` and an evidence URL was fetched. `needs_human_verification` lists the fields the extractor would not assert.

`composio_coverage` is a copy of the matcher result. Do not describe a missing toolkit as lack of an API, and do not describe a toolkit as free access.

Buildability is `Unknown` unless both an API type and an access statement were found on a fetched page. `Blocked` is used only when the fetched text says there is no public API.

## Verify before citing accuracy

```bash
.venv\Scripts\python.exe -m src.verification.framework --app-id 1 --field api_surface --verdict partially_correct --evidence-url URL --notes "What was wrong."
```

`data/verification_results.json` stays at `accuracy: null` until a person records a check. Do not publish an accuracy percentage from unverified rows.

## Secrets

Do not print `.env`. Do not commit `.env` or `.venv`. The research modules do not load the Composio key.

## Still open

The HTML case-study page is not part of this pipeline. After the 100-app run, review low-confidence rows before writing conclusions.

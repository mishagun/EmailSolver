# Changelog

All notable changes to EmailSolver are documented here.

## Format

- Every change gets a timestamped entry: `[HH:MM]`
- Commits are marked with `--- COMMIT: <short hash> "<message>" ---` so future agents can map changes to git history
- Entries between two commit markers are uncommitted changes
- Newest entries at the top within each date

---

## 2026-03-03

--- COMMIT: a6aabcc "Add deployment logic, concurrent classification, Gmail user labels, and E2E tests" ---

[21:50] Created CHANGELOG.md with timestamped format and commit checkpoint markers

[21:48] Created `.claude/settings.json` with Stop hook to enforce CHANGELOG updates

[21:45] Created `CLAUDE.md` — project guidelines, architecture, design decisions, coding conventions, documentation requirements

[21:44] Updated docs to reflect all changes:
- `docs/architecture.md` — concurrent classification, user labels, non-blocking actions, tenacity retry
- `docs/api.md` — user labels for move_to_category, multiple actions per email, fixed redirect code (307)
- `docs/frontend-guide.md` — user labels, multiple actions per email
- `README.md` — receipts category, Docker deployment with migrations

[21:40] Removed `action_taken` blocking in `analysis_service.py` — actions are no longer mutually exclusive, multiple actions can be applied to the same emails

[21:38] Replaced Gmail system category labels with Gmail user labels for `move_to_category`:
- Added `get_or_create_label` to `BaseEmailService` protocol and `GmailService`
- Removed `CATEGORY_TO_LABEL` mapping from `analysis_service.py`
- Labels created with category name directly (e.g., `promotions`, `receipts`)

[21:35] Added `receipts` to `BASE_CATEGORIES` in `classification_service.py`

[21:30] Added concurrent classification in `analysis_service.py`:
- Batches of 20 processed 3 at a time (`CLASSIFICATION_CONCURRENCY = 3`)
- Uses `asyncio.gather` + semaphore

[21:25] Added tenacity retry for Anthropic API calls in `classification_service.py`:
- Retries on 429 (rate limit) and 529 (overloaded) with exponential backoff
- Added `_extract_json()` helper for markdown code fences and non-text blocks
- Added logging (request/response details, retry warnings)

[21:20] Fixed `cwd` for alembic subprocess in `test_all.py` and `test_auth_flow.py` — resolves project root via `Path(__file__)`

[21:15] Created `scripts/test_all.py` — 11-step E2E test: migrations, health, auth URL, unauth blocked, browser OAuth, auth status, emails+stats, analysis lifecycle, analysis list, apply actions, delete+logout

[21:10] Deployment setup:
- Updated `alembic/env.py` — override `sqlalchemy.url` with `DATABASE_URL` env var
- Added `HEALTHCHECK` to `Dockerfile` using python urllib
- Added `migrations` one-shot service to `docker-compose.yml` with `DATABASE_URL` override
- App depends on `migrations: service_completed_successfully`
- Added `ANTHROPIC_API_KEY` to `.env.example`
- Created `scripts/deploy.sh` — validates .env, builds, starts, polls health

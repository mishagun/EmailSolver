# Changelog

All notable changes to EmailSolver are documented here.

## Format

- Every change gets a timestamped entry: `[HH:MM]`
- Commits are marked with `--- COMMIT: <short hash> "<message>" ---` so future agents can map changes to git history
- Entries between two commit markers are uncommitted changes
- Newest entries at the top within each date

---

## 2026-03-05

[16:20] Fix two HIGH security vulnerabilities in TUI:
- `tui/app.py`: `save_token` now sets `mode=0o700` on token directory and `chmod(0o600)` on token file to prevent world-readable JWT.
- `tui/screens/login.py`: Added `_OAUTH_TIMEOUT_SECONDS = 120`. Server timeout + deadline-based async loop prevent indefinite hangs when user abandons browser flow.
- `tests/tui/test_screens.py`: Added `mock.timeout` support and `test_save_token_sets_owner_only_permissions`.

[16:10] Fix HIGH security vulnerabilities: insecure defaults and JWT revocation:
- `app/core/config.py`: Added `field_validator` for `jwt_secret_key` (min 32 chars), `fernet_key` (required), and `jwt_algorithm` (HS256/HS384/HS512 allowlist). Removed insecure default.
- `app/core/security.py`: Added `jti` (UUID) claim to every JWT. `decode_jwt` checks denylist. New `revoke_jwt` method for logout revocation.
- `tests/test_security.py`, `tests/conftest.py`: Updated JWT secret to 32+ chars. Added jti and revocation tests.

[16:00] Fix two CRITICAL OAuth security vulnerabilities:
- `app/services/auth_service.py`: Server-side TTL state store. Code verifier no longer in state URL.
- `app/api/routes/auth.py`: `callback_port` range validation (1024-65535) at both `/login` and `/callback`.
- `tests/test_auth_routes.py`: 6 new tests for port validation and state rejection.

[15:30] Update auth route tests for redirect-based callback:
- `tests/test_auth_routes.py`: Callback tests now assert on 307 redirect + location header instead of JSON. Added `test_login_embeds_callback_port_in_state`, `test_callback_with_callback_port_redirects_to_localhost`, `test_success_renders_html_with_token`. Extracted `_mock_auth` helper.

[15:00] Rewrite OAuth callback as always-redirect pattern:
- `app/api/routes/auth.py`: `/callback` always returns `RedirectResponse` — to `localhost:{port}` with callback_port or to `/auth/success` without. New `/auth/success` endpoint serves HTML with token. Removed `AuthCallbackResponse`. Login endpoint embeds `callback_port` in OAuth state via `_CALLBACK_STATE_PREFIX`.
- `tui/screens/login.py`: Replaced token input with "Login with Google" button. Starts local `HTTPServer` to receive OAuth callback, opens browser, polls for token, validates via `/auth/status`.
- `tui/config.py`: Added `callback_port: int = 0` (env: `EMAILSOLVER_TUI_CALLBACK_PORT`).
- `tui/client.py`: `get_login_url` accepts `callback_port` parameter.
- `tests/tui/test_screens.py`: Rewrote `TestLoginScreen` for OAuth flow with mocked HTTPServer and webbrowser.

[14:00] Add sender grouping, bulk sender actions, and real RFC 8058 unsubscribe:
- `alembic/versions/b2c3d4e5f6g7_add_unsubscribe_headers.py` (new): Migration adds `unsubscribe_header` and `unsubscribe_post_header` Text columns to `classified_emails`.
- `app/models/db.py`: Added `unsubscribe_header` and `unsubscribe_post_header` columns to `ClassifiedEmail`.
- `app/models/schemas.py`: Added unsubscribe header fields to `EmailMetadata` and `ClassifiedEmailResponse`; new `SenderGroupSummary` schema.
- `app/core/protocols.py`: Added `get_sender_summary` abstract method to `BaseClassifiedEmailRepository`.
- `app/repositories/classified_email_repository.py`: Implemented `get_sender_summary` with GROUP BY sender_domain aggregation.
- `app/services/gmail_service.py`: Captures `List-Unsubscribe-Post` header; passes both raw headers to `EmailMetadata`.
- `app/services/analysis_service.py`: Passes unsubscribe headers to DB records; split `unsubscribe` action from `mark_spam` — tries RFC 8058 HTTP POST first, archives on success, falls back to spam on failure.
- `app/services/unsubscribe_service.py` (new): `parse_unsubscribe_urls` extracts HTTP URLs from headers; `attempt_http_unsubscribe` does one-click POST.
- `app/api/routes/analysis.py`: New `GET /{analysis_id}/senders?category=` endpoint; includes unsubscribe headers in response.
- `tui/models.py`: Mirrored schema changes + `SenderGroupSummary` model.
- `tui/client.py`: Added `get_sender_groups` method.
- `tui/screens/analysis.py`: New Senders tab with `g` binding; `u` binding for unsubscribe; sender-scoped actions; 3-tab navigation (Summary → Emails → Senders).
- `tui/screens/email_detail.py`: Unsubscribe display now shows "Yes (one-click)" / "Yes (link only)" / "No".
- `tui/styles/app.tcss`: Added senders table styling.
- `tests/test_unsubscribe_service.py` (new): 9 tests for URL parsing and HTTP unsubscribe.
- `tests/test_analysis_service.py`: Updated unsubscribe tests for new behavior (3 tests: fallback-to-spam, HTTP-success-archives, HTTP-failure-spam).

[10:30] Fix analysis fetching read emails by default:
- `app/models/schemas.py`: Changed `AnalysisCreateRequest.query` default from `""` (all emails) to `"is:unread"` so analyses only process unread emails unless explicitly overridden.
- `tests/test_analysis_routes.py`: Added `test_defaults_to_unread_query` to verify the route uses `"is:unread"` when no query is provided.

## 2026-03-04

[15:40] Improve README with step-by-step self-hosting guide:
- `README.md`: Replaced terse "Quick Start" with detailed "Self-Hosting Guide" — Google Cloud setup, Anthropic key, `.env` configuration with inline examples, Docker alternative, and privacy note explaining data flow.

[15:15] Improve Anthropic API resilience — more retries and longer timeouts:
- `app/services/classification_service.py`: Anthropic client now uses `max_retries=5` (was 2) and `timeout=120s` (was 60s default). Tenacity retry increased to 6 attempts (was 3) with max backoff of 60s (was 16s). Keeps concurrency=3 for speed.

[15:45] Tab key switches between Summary/Emails panes directly:
- `tui/screens/analysis.py`: Added `tab` binding with `priority=True` that toggles between `tab-summary` and `tab-emails`. Combined with auto-focus handler, Tab now jumps straight to the other table without stopping at the tab header bar.

[14:50] Auto-focus data tables in analysis screen:
- `tui/screens/analysis.py`: On mount, focus the summary table immediately instead of tab headers. Added `on_tabbed_content_tab_activated` handler to focus the corresponding DataTable when switching tabs. Tab headers remain navigable via Tab/arrows.

[14:45] Improve Escape navigation UX in analysis screen:
- `tui/screens/analysis.py`: Escape on Emails tab now returns to Summary tab (not dashboard), clears email filter, restores cursor to the previously selected category row, and focuses the summary table. Escape on Summary tab pops back to dashboard as before.

[14:30] Fix classification pipeline robustness — per-batch error handling and diagnostics:
- `app/services/analysis_service.py`: Wrapped `_classify_batch` in try/except so one failed batch doesn't kill the entire analysis. Added warning log when AI returns fewer results than batch size (mismatched IDs). Added summary log after classification. Early-fail with "failed" status if zero emails classified.
- `app/services/classification_service.py`: Added truncation detection — warns when `stop_reason != "end_turn"` (e.g. max_tokens hit). Improved log to show results vs input count.
- `app/models/schemas.py`: Changed `AnalysisCreateRequest.query` default from `"is:unread"` to `""` to match new TUI switch behavior.

[14:15] Add "Unread Only" toggle to TUI dashboard and fetch logging:
- `tui/screens/dashboard.py`: Added `Switch(value=True, id="unread-only-switch")` — ON by default, prepends `is:unread` to query. Query input default changed from `"is:unread"` to empty with placeholder.
- `app/services/gmail_service.py`: Added logging to `_list_messages_sync` (IDs returned vs requested + query) and `_get_messages_batch_sync` (fetched vs requested count) for diagnosing count mismatches.

[13:30] TUI: show logged-in email and category-filtered email browsing:
- `EmailSolverApp.user_email` stored on auth (both `check_auth` and login flow)
- Analysis screen header shows user email on the right
- Enter on a summary category row → switches to Emails tab filtered to that category
- `a` keybinding to clear filter and show all emails
- Filter label above emails table shows `showing: <category> (N emails)` or `showing: all (N emails)`
- Dashboard no longer makes redundant `get_auth_status` call (uses `email_app.user_email`)

[13:00] Minimal TUI redesign — keyboard-driven, monochrome:
- Removed `Header` widget from all screens (Footer with keybindings is sufficient)
- Removed colored action buttons from analysis screen (use `k`/`m`/`v`/`s` keybindings instead)
- Stripped all `variant="primary|success|warning|error"` from remaining buttons
- Removed decorative borders, colored text, uppercase labels throughout CSS
- Login screen: removed "Open Browser" button, added `o` keybinding instead
- Analysis screen: action keys changed from `1/2/3/4` to `k/m/v/s` (numbers conflict with TabbedContent tab switching)
- Updated tests to match (action test uses direct method call, login test updated for new text)

[11:45] Changed SQLAlchemy `echo` in `app/core/database.py` from `app_env == "development"` to `log_level == "DEBUG"` — SQL queries only logged when explicitly debugging, not on every dev deployment

[11:30] Added centralized logging configuration:
- Created `app/core/logging.py` with `setup_logging()` — configures root logger with clean formatter, quiets noisy third-party loggers (sqlalchemy, httpcore, googleapiclient) to WARNING
- Added `log_level: str = "INFO"` to `AppConfig` in `app/core/config.py` — controllable via `LOG_LEVEL` env var
- Called `setup_logging()` at module level in `app/main.py` so all INFO/DEBUG logs are no longer silently dropped

[11:20] Fix `move_to_category` not actually moving emails (`analysis_service.py`):
- Added `remove_labels=["INBOX"]` to the `modify_messages` call so emails are removed from inbox when moved to a category label
- Previously only added the label without removing from INBOX, so emails stayed in inbox and labels appeared empty

[11:15] Fix "Invalid label name" error in `move_to_category` action (`analysis_service.py`):
- Skip label creation for "primary" (emails stay in inbox, no label needed)
- Map reserved names ("spam", "trash", "inbox") to Gmail system labels instead of trying to create user labels
- Added `GMAIL_SYSTEM_LABEL_MAP` and `SKIP_LABEL_CATEGORIES` constants

[02:30] Refactored TUI screen architecture for clean design:
- `tui/screens/__init__.py` — Added `AppScreen` and `AppModalScreen` base classes with typed `email_app`, `client`, `tui_config` properties (eliminates `type: ignore` comments)
- `tui/app.py` — Imports all screens at top level, added `navigate_to_dashboard()`, `navigate_to_login()`, `push_analysis_screen()` navigation methods (eliminates deferred imports)
- `tui/screens/analysis.py` — Uses `AppScreen` base, `self.client` and `self.tui_config` instead of `self.app.client # type: ignore`
- `tui/screens/email_detail.py` — Uses `AppModalScreen` base
- `tui/screens/login.py` — Uses `AppScreen` base, delegates navigation to `self.email_app`
- `tui/screens/dashboard.py` — Uses `AppScreen` base, delegates navigation to `self.email_app`

[01:45] Added Terminal UI (TUI) built with Python Textual:
- `tui/models.py` — Pydantic models mirroring backend schemas for decoupling
- `tui/config.py` — TUI configuration with `EMAILSOLVER_TUI_` env prefix
- `tui/client.py` — Typed async httpx client wrapping all API endpoints with `ApiError` exception
- `tui/app.py` — Main Textual App with token persistence at `~/.emailsolver/token`
- `tui/screens/login.py` — Login screen: browser OAuth + JWT paste input
- `tui/screens/dashboard.py` — Dashboard: inbox stats, analyses table, new analysis form
- `tui/screens/analysis.py` — Analysis view: live progress polling, category summary, email table, action buttons
- `tui/screens/email_detail.py` — Modal with full email classification details
- `tui/styles/app.tcss` — Textual CSS for all screens
- `tui/__main__.py` — Entry point (`python -m tui` or `emailsolver-tui`)
- `pyproject.toml` — Added `[project.scripts]` entry, `tui` optional dependency, package discovery for `app*` + `tui*`
- 55 tests in `tests/tui/` — models, config, client (mocked httpx), all 4 screens (Textual Pilot)
- Updated `README.md` with TUI section, setup instructions, and project structure

[00:15] Added integration test suite (`tests/integration/`):
- `fakes.py` — `FakeEmailService`, `FakeClassificationService`, `FakeAuthService` implementing protocol interfaces with deterministic behavior
- `conftest.py` — integration fixtures wiring real services + fake externals against test database
- `test_analysis_lifecycle.py` — 7 tests: full analysis flow, empty inbox, failure handling, DB persistence, category actions, list/delete
- `test_apply_actions.py` — 6 tests: move_to_category, mark_read, mark_spam, specific email IDs, incomplete analysis rejection, keep noop
- `test_auth_flow.py` — 6 tests: callback user creation, status after login, logout token clearing, unauthenticated rejection, login redirect, repeated login idempotency

[00:20] Added containerized test runner:
- `Dockerfile.test` — includes dev dependencies (`--group dev`)
- `docker-compose.test.yml` — spins up postgres + test runner, passes `TEST_DATABASE_URL` to container
- Run with: `docker compose -f docker-compose.test.yml up --build --abort-on-container-exit`

[00:10] Fixed pre-existing unit test failures:
- `test_classification_service.py` — replaced `MagicMock` content blocks with real `TextBlock` instances (fixes `isinstance` check in `_extract_json`)
- `test_analysis_service.py` — fixed `test_apply_move_to_category` to match actual `get_or_create_label` + `modify_messages` call signature (no `remove_labels`)
- `test_analysis_service.py` — fixed `test_apply_actions_skips_already_applied` → renamed to `test_apply_actions_reapplies_even_if_already_applied` (actions are not mutually exclusive by design)
- Added `get_or_create_label` mock to default `_build_service` helper

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

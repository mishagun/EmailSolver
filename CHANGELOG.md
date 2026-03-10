# Changelog

All notable changes to EmailSolver are documented here.

## Format

- Every change gets a timestamped entry: `[HH:MM]`
- Commits are marked with `--- COMMIT: <short hash> "<message>" ---` so future agents can map changes to git history
- Entries between two commit markers are uncommitted changes
- Newest entries at the top within each date

---

## 2026-03-10

- [--:--] Build Docker images in CI (GHCR) instead of on EC2 — prevents OOM on t2.micro. New `build-and-push` job builds app + web images, deploy just pulls them (`deploy.yml`, `docker-compose.yml`)
- [--:--] Add memory limits to all containers: postgres 256m, app 384m, web 64m, db-backup 64m (`docker-compose.yml`)
- [--:--] Tune Postgres for low-memory: shared_buffers=64MB, work_mem=2MB, maintenance_work_mem=32MB (`docker-compose.yml`)
- [--:--] Fix deploy workflow hanging again: use SCP to copy .env file instead of passing secret through SSH script (drone-ssh hangs on multiline secrets with special chars)
- [--:--] Fix deploy workflow hanging: split .env write into separate SSH step (removes `envs` passthrough that caused drone-ssh to hang on multiline secrets), add `command_timeout: 10m` to deploy step and `30s` to env write step (`.github/workflows/deploy.yml`)
- [--:--] Expand LoginPage with feature grid (scan/classify/act/undo descriptions) and footer matching Layout (`web/src/pages/LoginPage.tsx`)
- [--:--] Add `docker-compose.local.yml` — simplified local dev compose without web/caddy/db-backup, exposes postgres:5432 and app:8000 directly
- [--:--] Change row selection color from cold blue (#e6ecff) to warm sand (#ece8d8) to match brutalist off-white aesthetic (`web/src/styles/variables.css`)
- [19:10] Fix actions applied to entire category instead of filtered sender: replace if/elif chain in `analysis.py` route with single `find_by_filters` call that dynamically combines WHERE clauses. Add `find_by_filters` to protocol and repository. Add unit test and integration test for combined sender_domain+category filter. Add second promotions sender to fake data for test coverage.
- [17:59] Redesign favicon: solid black envelope with off-white fold lines, no checkmark and link in index.html (`web/public/favicon.svg`, `web/index.html`)
- [17:56] Fix footer links to inherit color instead of default blue, add MIT LICENSE file
- [17:54] Add footer to Layout with "developed by mike feldman" + LinkedIn and GitHub links (`web/src/components/Layout.tsx`)
- [17:52] Improve DashboardPage with inline descriptions: richer text for inbox scan and ai analysis cards explaining what each does and auto-apply behavior, added explanation text below auto-apply checkbox (`web/src/pages/DashboardPage.tsx`)

- [--:--] Restyle checkboxes in web frontend: replaced default browser checkboxes with custom brutalist style — no shadows, white background, 1px black border, no border-radius, solid black fill with white checkmark when checked (`web/src/styles/global.css`)

[17:55] Fix action badges stacking vertically: added `.actions-inline` CSS class with `white-space: nowrap` and compact badge sizing. Applied to SummaryTab and SendersView "actions applied" columns. Rows now stay single-height regardless of action count.

[17:53] Fix undo never available: replaced `useRef`+`useState` sync approach with pure `useState` for undo stack. Fixed stale closure in keyboard handler by using stable refs (`handleSelectionActionRef`, `handleToggleRef`, `fetchAnalysisRef`) updated on every render. Keyboard shortcuts now always use latest state.

[17:51] Add multi-select: checkbox column in EmailsTable, SummaryTab, and SendersView with select-all header checkbox. Selection state (`selectedEmails`, `selectedCategories`, `selectedSenders`) clears on tab/filter change. ActionBar scope shows "{n} selected" when items are checked. Actions apply to selected items when selection exists, else fall back to current filter scope.

[17:49] Add immediate visual feedback: `flash-action` CSS animation (blue flash, 0.4s) applied to affected rows when action is applied. Flash IDs tracked via `flashIds` state with auto-clear timeout. Works on email rows, category rows (via child email IDs), and sender rows.

[17:47] Add 14 AnalysisPage tests covering: category checkboxes, email multi-select, select-all, scope display, undo enable/disable, action API params, undo API params, selected-only actions, selection clearing, inline badge rendering. Updated ActionBar tests (8 total) for undo button states and tooltips. Updated HoverActions tests (4 total) confirming no undo button and tooltips present.

[17:40] Restyle insights charts: replace flat blue (#0055ff) fills with cold faded palette. Category bars now use distinct muted colors per bar (`CATEGORY_PALETTE`). Timeline uses `#a8b5c8`, senders use `#8a9bae`, confidence uses `#8a9bae`. Action pie colors updated to softer tones (`#7a9cc6` read, `#7aab7a` moved, `#c47a7a` spam/unsub).

[17:37] Add insights tab to web AnalysisPage with recharts visualizations: overview stat cards (total emails, categories, senders, avg confidence, unsub opportunities), category distribution bar chart (clickable), email volume timeline (last 14 days), top 10 senders horizontal bar chart, action breakdown pie chart, confidence distribution histogram. All charts styled with brutalist aesthetic (IBM Plex Mono, no rounded corners, 1px solid borders, matching CSS variable colors). New files: `web/src/components/insights/InsightsTab.tsx`, `StatCard.tsx`, `insights.css`. Modified `AnalysisPage.tsx` to add `insights` tab. Added `recharts` dependency. 9 tests in `InsightsTab.test.tsx`.

[22:15] Fix unsubscribe: emails without `has_unsubscribe` are now skipped instead of being marked as spam. Split `classified_emails` into `unsubscribable` (has headers) and `skipped` (no headers). Only emails with unsubscribe capability get `action_taken` recorded. Backend logs skipped count.

[22:10] Redesign undo as page-level action: removed undo button from HoverActions and EmailDetailModal. Undo now uses a frontend undo stack (`undoStackRef` in AnalysisPage) that records `{action, emailIds}` for each action. Pressing `z` or clicking `[z] undo` in ActionBar pops the stack and sends undo for those specific email_ids. ActionBar undo button disabled when stack is empty (`canUndo` prop).

[21:45] Add `email_action_history` table (migration `18db2440cd0b`) for full action audit trail per email. Every action now records a history entry via `bulk_record_action`. Undo (`pop_last_action`) removes the latest entry, restores `action_taken` to the previous action (or None). Multi-level undo supported. Updated protocol, repository, analysis_service, and all test mocks.

[21:40] Remove misleading undo symbol (↩/⎌) from per-email HoverActions.

[21:30] Fix hover actions CSS: replaced unreliable `tr { position: relative }` with `.hover-actions-cell` class on the `<td>`, making absolute positioning reliable across browsers (especially Safari). Added `white-space: nowrap` and `cursor: pointer` to hover action buttons.

[21:25] Add undo action (`z` key): backend `ActionType.UNDO` in `schemas.py`, undo logic in `analysis_service.py` that reverses Gmail changes (mark_spam→remove SPAM/add INBOX, mark_read→add UNREAD, move_to_category→remove label, unsubscribe→add INBOX/remove SPAM). Updated `protocols.py` and `classified_email_repository.py` to accept `action_taken: str | None`. Frontend: added undo to `types.ts`, `HoverActions.tsx`, `ActionBar.tsx`, `EmailDetailModal.tsx`, keyboard map in `AnalysisPage.tsx`.

[21:20] Add tooltips to all action buttons (HoverActions + ActionBar) explaining what each action does via `title` attribute.

[21:15] Add "actions applied" column to SummaryTab (categories view) and SendersView (group by sender) showing colored badges with counts per action type (e.g. `spam: 3`, `read: 5`). Both components now receive `emails` prop to compute action counts via `useMemo`.

[21:10] Document nvm workaround in CLAUDE.md: always use absolute paths (`/Users/mikhail_f/.nvm/versions/node/v22.16.0/bin/node`) instead of bare `node`/`npx`/`npm` to avoid nvm lazy-loading shell function hang.

[20:15] Extract hardcoded Postgres credentials from `docker-compose.yml` into `.env` variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`). All services now reference `${VAR}` interpolation. Updated `.env` and `.env.example` with the new vars. Backup retention/interval also configurable via env with defaults.

[20:00] Add automated database backup service (`db-backup`) to `docker-compose.yml` — runs `pg_dump` daily with 7-day retention, writes to `./backups/` bind mount. Added `scripts/db_restore.sh` restore script, `backups/` to `.gitignore`, documented backup strategy in `CLAUDE.md` Deployment section.

[18:30] Web frontend: Add "inbox scan" analysis type support. `types.ts`: added `analysis_type` to `AnalysisResponse` and `AnalysisCreateRequest`. `DashboardPage.tsx`: replaced single "new analysis" form with two launcher cards (inbox scan + ai analysis) side by side, shared options row below, and type column in analyses table. `AnalysisPage.tsx`: hide priority column in EmailsTable and show dash for recommended actions in SummaryTab when `analysis_type === 'inbox_scan'`; added type badge in analysis header.

[18:00] TUI: Add "Inbox Scan" analysis type support. Added `AnalysisType` enum and `analysis_type` field to `AnalysisResponse`/`AnalysisCreateRequest` in `tui/models.py`. Dashboard (`tui/screens/dashboard.py`) now has two buttons ("Start Inbox Scan" / "Start AI Analysis") replacing the single "Start" button, and analyses table shows a "Type" column. Categories input only used for AI analysis. Analysis screen (`tui/screens/analysis.py`) shows "--" for priority column when analysis is inbox_scan type.

[16:05] Add visual action feedback + hover action menus to web frontend. Email rows now show colored left borders, reduced opacity, and strikethrough (spam/unsub) based on `action_taken`. Raw action text replaced with colored badges. Hover over any row in Summary/Emails/Senders tabs reveals inline action buttons (k/m/v/s/u). New files: `HoverActions.tsx`, `utils/actionDisplay.ts`. Updated: `variables.css` (action colors), `global.css` (row/badge/hover styles), `AnalysisPage.tsx` (all 3 tabs + handleAction overrides), `EmailDetailModal.tsx` (action badge). Added 7 new tests (HoverActions: 3, actionDisplay: 3, EmailDetailModal: 1 updated). All 56 tests pass.

[14:00] Add React web frontend (`web/`) — full SPA with React 18, TypeScript, Vite, React Router v6. Pages: LoginPage, CallbackPage, DashboardPage, AnalysisPage (3-tab: Summary/Emails/Senders). Components: Layout, ActionBar, AnalysisProgress, EmailDetailModal. API client (`api/client.ts`) mirrors `tui/client.py`. Auth via `AuthContext` with localStorage JWT persistence. Design: IBM Plex Mono, brutalist aesthetic, lowercase throughout, warm off-white palette.

[14:00] Backend: add `web_app_url` config field (`app/core/config.py`) and `redirect_url` query param to `/auth/login` + `/auth/callback` (`app/api/routes/auth.py`). Validates redirect_url starts with configured `web_app_url` to prevent open redirects. Embeds redirect_url in OAuth state, extracts on callback to redirect with JWT token.

[14:00] Add 49 frontend tests (9 test files) — Vitest + Testing Library + jsdom: API client tests (11), AuthContext tests (4), usePolling hook tests (5), ActionBar tests (4), AnalysisProgress tests (3), EmailDetailModal tests (10), LoginPage tests (3), CallbackPage tests (3), DashboardPage tests (6).

## 2026-03-05

[20:30] Fix OAuth "Invalid or expired OAuth state" bug — `get_auth_service()` in `dependencies.py` was creating a new `GoogleAuthService` instance per request, so the state stored during `/login` was lost by the time `/callback` fired. Made the auth service a module-level singleton (`_auth_service`) so the in-memory state store persists across requests.

[20:00] TUI UX improvements — 4 issues addressed:
- Issue 4: Make `category` optional in senders stack — `protocols.py`, `classified_email_repository.py`, `analysis.py` (route), `client.py`, `analysis.py` (screen) all accept `category: str | None = None`. Senders tab now loads all senders when no category selected.
- Issue 2: Per-email actions in `EmailDetailScreen` — rewrite with k/m/v/s/u keybindings, `analysis_id` parameter, `_apply_action()` worker, `#detail-status` feedback widget. `AppModalScreen` gains `client` property.
- Issue 1: Crowded footer — action keys hidden from Footer (`show=False`), new `#action-help-bar` Static widget shows contextual hints per active tab.
- Issue 3: Horizontal overflow — `#analysis-view` gets `overflow-x: hidden`, `#email-detail` uses `width: 90%; max-width: 80` instead of fixed `width: 72`, sender column truncated to 30 chars.
- Fixed `tests/tui/test_screens.py` to pass `analysis_id=1` to `EmailDetailScreen`.

[17:15] Merge security tests and docs agents, resolve CHANGELOG conflicts, clean up worktree branches. 191 tests passing.

[17:00] Add comprehensive security tests for auth state store, config validators, and JWT revocation:
- `tests/test_auth_service.py` (NEW): 10 tests covering GoogleAuthService state store — stores state on start_authorization, consumes on exchange_code (one-time use), rejects unknown/replayed state, cleans up expired entries on both start_authorization and exchange_code, verifies code_verifier passed to flow, thread safety with 10 concurrent workers.
- `tests/test_config.py` (NEW): 13 tests covering AppConfig validators — rejects short/empty JWT secret, rejects empty fernet key, rejects invalid/asymmetric JWT algorithms (none, RS256), accepts all valid HS* algorithms and valid keys.
- `tests/test_security.py` (MODIFY): Added 3 tests to TestJWT — unique jti per token for same user, revoked token rejected while new token for same user still works, denylist cleanup removes expired entries when new revocation triggers cleanup.
- `tests/test_auth_routes.py` (MODIFY): Added test_callback_rejects_failed_credentials (null token returns 400), test_callback_tokens_encrypted_in_db (access/refresh tokens never stored in plaintext), test_logout_clears_token_expiry (token_expiry set to None on logout).

[16:55] Fix slow analysis — eliminate double retries, respect rate-limit headers:
- `app/services/classification_service.py`: Set `max_retries=0` on Anthropic client (was 5) to eliminate double retry loop. Replaced `wait_exponential` + `_log_retry` with `_wait_for_rate_limit` that reads the `retry-after` header from 429 responses and waits exactly that long. Falls back to exponential backoff for 529s.
- `app/services/analysis_service.py`: Reduced `CLASSIFICATION_CONCURRENCY` from 3 to 2 to avoid triggering rate limits in the first place.

[16:30] Document security hardening in CLAUDE.md, docs/architecture.md, docs/api.md, docs/frontend-guide.md: OAuth state store, JWT revocation, config validation, token file permissions, port validation constraints.

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

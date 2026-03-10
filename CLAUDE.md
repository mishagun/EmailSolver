# EmailSolver — Project Guidelines

## Architecture

- **Clean Architecture** with clear layer separation: routes -> services -> repositories -> database
- **Protocol-based abstractions** (`app/core/protocols.py`) — all services implement abstract base classes for testability and dependency inversion
- **Dependency injection** via FastAPI's `Depends()` (`app/core/dependencies.py`) — services are wired up here, not instantiated in business logic
- **Repository pattern** — data access is isolated behind repository interfaces; two patterns coexist:
  - Session-injected (request-scoped)
  - Session-maker (for background tasks that outlive the request)

## Key Design Decisions

- **Gmail user labels** (not system category labels) for `move_to_category` — labels are created via `get_or_create_label` with the category name directly (e.g., `promotions`, `receipts`). No label prefixes.
- **Actions are not mutually exclusive** — `action_taken` tracks what was applied but does not block subsequent actions. Users can `move_to_category` then `mark_read` on the same emails.
- **Concurrent classification** — batches of 20 emails are classified in parallel (`CLASSIFICATION_CONCURRENCY = 3` in `analysis_service.py`) using `asyncio.gather` + semaphore
- **Retry with tenacity** — Anthropic API calls retry on 429 (rate limit) and 529 (overloaded) with exponential backoff, configured in `classification_service.py`
- **JSON extraction from Claude responses** — `_extract_json()` in `classification_service.py` handles markdown code fences and non-text content blocks
- **Base categories**: `primary`, `promotions`, `social`, `updates`, `spam`, `newsletters`, `receipts` — AI can create additional categories dynamically
- **No hard cap on email count** — the system handles thousands of emails through batched Gmail fetching (50/batch), concurrent classification (20/batch, 3 concurrent), and bulk Gmail actions (1000/batch)
- **Unsubscribe headers stored raw** — `classified_emails.unsubscribe_header` and `unsubscribe_post_header` hold the raw `List-Unsubscribe` and `List-Unsubscribe-Post` header values from Gmail. `has_unsubscribe` remains a boolean convenience flag.
- **Real RFC 8058 one-click unsubscribe** — when `unsubscribe` action is applied, emails with `unsubscribe_post_header` + HTTP URL in `unsubscribe_header` get an HTTP POST attempt. On success: archive (remove INBOX). On failure: fall back to mark as spam + remove INBOX. All get `action_taken="unsubscribe"`.
- **Sender grouping** — `GET /analyses/{id}/senders?category=` returns `SenderGroupSummary` (domain, display name, count, has_unsubscribe) via `GROUP BY sender_domain` in the classified_email_repository. Stateless module `unsubscribe_service.py` has no ABC — just two functions.
- **OAuth state store** — server-side `dict` with `threading.Lock` and 10-min TTL. Nonces are consumed on first use (replay protection). PKCE `code_verifier` stays server-side only.
- **Config fails fast on weak secrets** — `jwt_secret_key` (min 32 chars), `fernet_key` (required), `jwt_algorithm` (allowlist: HS256/HS384/HS512) validated via Pydantic `field_validator`. App won't start with insecure defaults.
- **JWT revocation via in-memory denylist** — `jti` claim on every token, checked in `decode_jwt`. `revoke_jwt` stores jti with remaining TTL. Single-process only; multi-process needs Redis.
- **Token file permissions** — `~/.emailsolver/token` written with `0o600`, directory with `0o700`.
- **Action history** — `email_action_history` table records every action per email with timestamp. `action_taken` on `classified_emails` is the denormalized "current" action. On undo, `pop_last_action` removes the latest history entry and restores `action_taken` to the previous one. Supports multi-level undo.

## TUI (Terminal UI)

- **Optional dependency**: `textual` lives under `[project.optional-dependencies] tui` — backend stays lightweight
- **Duplicate models**: `tui/models.py` mirrors `app/models/schemas.py` for decoupling (future repo split)
- **Token persistence**: JWT saved at `~/.emailsolver/token`, loaded on startup
- **Auth flow**: Browser OAuth → user copies JWT from JSON response → pastes in TUI Input widget
- **Config**: `TuiConfig` with `EMAILSOLVER_TUI_` env prefix, `.env` file support
- **Polling**: `set_interval` in AnalysisScreen while status is `pending`/`processing`, stops on `completed`/`error`
- **Screen navigation**: LoginScreen → DashboardScreen → AnalysisScreen ↔ EmailDetailScreen (modal)
- **AnalysisScreen has 3 tabs**: Summary → Emails → Senders. Navigation: `Tab` cycles tabs; `Enter` on Summary selects category and jumps to Emails; `g` on Emails opens Senders tab for current category; `Enter` on Senders filters Emails by sender_domain; `Escape` goes back one level (Senders→Emails→Summary→pop).
- **Sender-scoped actions**: When on Senders tab, action keys (k/m/v/s/u) apply to `sender_domain` instead of `category`.
- **Per-email actions in detail modal**: `EmailDetailScreen` takes `analysis_id` kwarg, has k/m/v/s/u keybindings that call `apply_actions(email_ids=[self.email.id])`. Mutates shared `email.action_taken` reference. `AppModalScreen` has `client` property.
- **Contextual help bar**: `#action-help-bar` Static widget docked above Footer, content updates via `_update_help_bar()` on tab change. Action keys hidden from Footer with `show=False`.
- **Senders without category**: `category` is optional (`str | None = None`) throughout — protocol, repository, route, client, screen. When `None`, senders tab shows all senders across categories.
- **Testing**: Textual `run_test()` + `Pilot` for screen tests; mock `httpx` for client tests

## Web Frontend

- **Tech stack**: React 18 + TypeScript + Vite + React Router v6
- **Design**: IBM Plex Mono monospace, brutalist aesthetic, all lowercase text (`text-transform: lowercase`), warm off-white (`#f8f7f4`), no rounded corners, 1px solid black borders
- **Auth flow**: Login → redirect to `{API_BASE}/api/v1/auth/login?redirect_url={WEB_BASE}/callback` → Google OAuth → backend redirects to `{WEB_BASE}/callback?token={jwt}` → stored in `localStorage`
- **`web_app_url` config**: Must be set in `.env` to enable web OAuth redirect. Backend validates `redirect_url` starts with this value (open redirect prevention).
- **API client**: `web/src/api/client.ts` — singleton `apiClient`, typed fetch wrapper mirroring `tui/client.py`
- **State management**: React Context (`AuthContext`) + component state. No external state library.
- **Routing**: `/login`, `/callback`, `/dashboard` (protected), `/analysis/:id` (protected). `ProtectedRoute` wrapper redirects to `/login` when unauthenticated.
- **Polling**: `usePolling` hook with `setInterval` + auto-cleanup for pending/processing analyses (2s interval)
- **Keyboard shortcuts**: `k/m/v/s/u` for actions, `Escape` to navigate back, `r` to refresh (disabled when input focused or modal open)
- **Testing**: Vitest + Testing Library + jsdom. Run via `npm test` in `web/`. Test utils in `web/src/test/`.
- **Dev**: `cd web && npm run dev` → `http://localhost:5173`. Set `VITE_API_BASE_URL` env var if backend is not at `http://localhost:8000`.

## Deployment

- `docker-compose.yml` has a `migrations` one-shot service that runs `alembic upgrade head` before the app starts
- `alembic/env.py` overrides `sqlalchemy.url` with `DATABASE_URL` env var when set (required for Docker where DB host is `postgres`, not `localhost`)
- `scripts/deploy.sh` — validates `.env`, builds, starts services, polls health
- `Dockerfile` includes a `HEALTHCHECK` using python urllib (no curl in slim image)
- **Database backups**: `db-backup` service runs `pg_dump` daily, writes gzipped custom-format dumps to `./backups/` bind mount, retains last 7. Restore via `scripts/db_restore.sh <file>`. Future: add S3 sync via cron or additional service.

## Testing

- **Unit tests** (`tests/`) — pytest + pytest-asyncio, mock external services via protocol abstractions
- **E2E scripts** (`scripts/`) — `test_all.py` runs 11 steps against a live server with real Gmail OAuth; `test_auth_flow.py` covers auth only. These require a real user and are not run in CI.
- NEVER create tests that check log messages using caplog. Log messages are implementation details. Test behavior and state changes instead.
- When writing tests, mock at the protocol boundary (e.g., mock `BaseEmailService`, not `gmail.build()`)

## Documentation

- **Every change must be documented.** When modifying behavior, update the relevant docs (`docs/architecture.md`, `docs/api.md`, `docs/frontend-guide.md`, this file) in the same session. Future developers (and future Claude sessions) rely on docs to understand what the system does and why.
- Update `CLAUDE.md` when making architectural or design decisions — this file is the primary source of truth for how the project works and what conventions to follow.
- `README.md` covers setup and public-facing info. `docs/` covers internals. Keep both in sync with actual behavior.
- Don't let docs drift — outdated docs are worse than no docs because they mislead.

### Changelog (`CHANGELOG.md`)

- **Every code change must have a timestamped entry** in `CHANGELOG.md`. A Stop hook enforces this.
- Format: `[HH:MM] description of what changed and why`
- Group under date headers: `## YYYY-MM-DD`
- Newest entries at the top within each date section.
- **Commit checkpoints:** When a commit is made, add a marker line:
  ```
  --- COMMIT: abc1234 "commit message here" ---
  ```
- Entries between two commit markers represent uncommitted changes. This lets future agents trace what was changed before/after each commit.
- Keep entries concise but specific — mention file names and the behavioral change, not just "updated code".

## Code Style

- All functions must have type hints
- Use keyword arguments for function calls
- No unnecessary docstrings or comments — code should be self-explanatory
- Use `kwargs` over positional args in function signatures
- Avoid over-engineering — no abstractions for one-time operations
- Follow existing patterns — check `protocols.py` before adding new service methods
- Ruff for linting (E, F, I, N, UP, B, SIM rules), mypy strict mode for type checking

## File Layout

```
app/
  api/routes/          # FastAPI route handlers (auth, analysis, emails)
  core/                # Config, database, protocols, security, DI
  models/              # SQLAlchemy models (db.py) + Pydantic schemas (schemas.py)
  repositories/        # Data access layer
  services/            # Business logic (analysis, classification, gmail, auth)
tui/
  screens/             # Textual screens (login, dashboard, analysis, email_detail)
  styles/              # Textual CSS (app.tcss)
  app.py               # Main Textual App, token persistence
  client.py            # Typed async httpx API client
  models.py            # Pydantic models (mirrors app/models/schemas.py)
  config.py            # TUI config (EMAILSOLVER_TUI_ env prefix)
  __main__.py          # Entry point: python -m tui
web/
  src/
    api/               # Typed fetch client + TS interfaces (mirrors tui/client.py)
    components/        # Reusable components (Layout, ActionBar, AnalysisProgress, EmailDetailModal)
    context/           # AuthContext (JWT in localStorage)
    hooks/             # useAuth, usePolling
    pages/             # LoginPage, CallbackPage, DashboardPage, AnalysisPage
    styles/            # CSS: variables.css, global.css, animations.css
    test/              # Test setup, fixtures, render utils
  vite.config.ts       # Vite + Vitest config
tests/                 # Pytest test suite
  tui/                 # TUI tests (models, client, config, screens)
alembic/               # Database migrations
docs/                  # API reference, architecture, frontend guide
scripts/               # Deployment + E2E test scripts (not CI)
```

## Common Workflows

- **Adding a new action type**: Add to `ActionType` enum in `schemas.py`, implement in `_apply_actions()` in `analysis_service.py`. On frontend: add to `ActionType` in `types.ts`, `HoverActions.tsx`, `ActionBar.tsx`, `EmailDetailModal.tsx`, keyboard map in `AnalysisPage.tsx`, and `actionDisplay.ts`.
- **Adding a new base category**: Add to `BASE_CATEGORIES` in `classification_service.py`
- **Adding a new API endpoint**: Add route in `app/api/routes/`, wire dependencies in `dependencies.py`, add protocol method if new service logic needed
- **Database changes**: `uv run alembic revision --autogenerate -m "description"` then `uv run alembic upgrade head`

## Node.js / nvm

- **CRITICAL**: nvm lazy-loading shell function intercepts `node`/`npx`/`npm` commands and dumps its help text, causing commands to hang or produce garbage output.
- **Always use absolute paths** for node commands:
  - Node: `/Users/mikhail_f/.nvm/versions/node/v22.16.0/bin/node`
  - npx: `/Users/mikhail_f/.nvm/versions/node/v22.16.0/bin/npx`
  - npm: `/Users/mikhail_f/.nvm/versions/node/v22.16.0/bin/npm`
- Example TypeScript check: `/Users/mikhail_f/.nvm/versions/node/v22.16.0/bin/node /Users/mikhail_f/.nvm/versions/node/v22.16.0/bin/npx tsc --noEmit`
- **Never** use `source ~/.nvm/nvm.sh`, `export NVM_DIR`, `nvm use`, or bare `node`/`npx`/`npm` — they all trigger the nvm help dump.

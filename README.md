# TidyInbox

AI-powered Gmail inbox cleaner. Scans your inbox, classifies emails into categories using Claude AI, and lets you bulk-apply actions (mark read, move, spam, unsubscribe) with full undo support.

## How It Works

1. **Scan** -- reads your inbox via Gmail API, extracts sender, subject, and metadata
2. **Classify** -- two-pass AI system: first classifies emails into categories, then verifies and recommends actions per category
3. **Act** -- bulk mark as read, move to category, mark spam, or one-click unsubscribe
4. **Undo** -- every action is reversible with full action history

Two analysis modes:
- **Inbox scan** -- fast, groups by Gmail's built-in categories. No AI needed.
- **AI analysis** -- classifies each email with Claude. Assigns categories, importance (1-5), sender type, confidence scores. Generates witty insights about your inbox.

## Features

- **Dynamic categories** -- base set (primary, promotions, social, updates, spam, newsletters, receipts) plus user-provided custom categories. AI can create new ones on the fly.
- **Batch API for large inboxes** -- 500+ emails use Anthropic Message Batches API (50% cheaper, processes in background)
- **Sender grouping** -- group emails by sender domain, apply actions per sender
- **AI insights** -- dry observations about your inbox patterns ("93% of your inbox is stuff no human wrote")
- **Real-time unsubscribe** -- RFC 8058 one-click HTTP POST unsubscribe, falls back to mark spam
- **OAuth with PKCE** -- server-side state store with replay protection
- **Concurrent classification** -- batches of 20, 2 concurrent, with retry on rate limits

## Interfaces

### Web Frontend

React + TypeScript + Vite. Brutalist design with IBM Plex Mono, all lowercase, warm off-white background.

```bash
cd web && npm install && npm run dev
# Opens at http://localhost:5173
```

Set `VITE_API_BASE_URL` if backend isn't at `http://localhost:8000`.

**Pages:** Login (Google OAuth) -> Dashboard (inbox stats, create analysis, analysis history) -> Analysis (categories/emails/insights tabs, action bar, keyboard shortcuts)

**Keyboard shortcuts:** `k` keep, `m` mark read, `v` move to category, `s` mark spam, `u` unsubscribe, `z` undo, `g` group by sender, `Escape` back, `r` refresh

### Terminal UI (TUI)

Built with [Textual](https://textual.textualize.io/). Full terminal interface with the same functionality as the web frontend.

```bash
# Install TUI dependencies
uv pip install -e ".[tui]"

# Run (backend must be running)
uv run python -m tui
```

**Flow:** Login (browser OAuth) -> Dashboard -> Analysis (Summary/Emails/Senders tabs) -> Email detail modal

**Configuration** via environment variables (prefix `TIDYINBOX_TUI_`):
| Variable | Default | Description |
|----------|---------|-------------|
| `TIDYINBOX_TUI_BASE_URL` | `http://localhost:8000` | Backend API URL |
| `TIDYINBOX_TUI_POLL_INTERVAL_SECONDS` | `2.0` | Analysis polling interval |

Token persisted at `~/.tidyinbox/token`.

## Tech Stack

- **Backend:** FastAPI, Python 3.13+, async/await
- **Database:** PostgreSQL + SQLAlchemy 2.0 (async)
- **AI:** Anthropic Claude via official SDK
- **Auth:** Google OAuth 2.0 with PKCE + JWT sessions
- **Email:** Gmail API (read, modify, label management, unsubscribe)
- **Web:** React 18, TypeScript, Vite, React Router v6
- **TUI:** Textual, httpx
- **Migrations:** Alembic
- **Security:** Fernet symmetric encryption for tokens, JWT revocation denylist
- **CI/CD:** GitHub Actions -> GHCR -> Docker Compose on EC2

## Self-Hosting

Your email data stays on your machine. Only email metadata (sender, subject, snippet) is sent to the AI provider for classification. Results are stored locally and expire after 7 days.

### Prerequisites

- Python 3.13+ (or Docker)
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for PostgreSQL, or bring your own)
- Google Cloud project (free) -- for Gmail API access
- Anthropic API key -- for email classification

### Step 1: Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a new project
2. Enable the **Gmail API**: APIs & Services > Library > search "Gmail API" > Enable
3. Configure the **OAuth consent screen**: APIs & Services > OAuth consent screen
   - Choose "External" user type
   - Fill in app name and your email
   - Add scopes: `gmail.readonly`, `gmail.modify`, `gmail.labels`
   - Add your Google account as a test user
4. Create **OAuth credentials**: APIs & Services > Credentials > Create Credentials > OAuth client ID
   - Application type: "Web application"
   - Authorized redirect URIs: `http://localhost:8000/api/v1/auth/callback`
   - Copy the **Client ID** and **Client Secret**

### Step 2: Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Create API Key, copy it

### Step 3: Install and Configure

```bash
git clone https://github.com/mishagun/EmailSolver.git
cd EmailSolver
uv sync --dev

# Start PostgreSQL
docker compose -f docker-compose.local.yml up -d postgres

# Configure
cp .env.example .env
```

Edit `.env`:

```bash
DATABASE_URL=postgresql+asyncpg://emailsolver:emailsolver@localhost:5432/emailsolver
JWT_SECRET_KEY=<openssl rand -hex 32>
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback
FERNET_KEY=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 4: Run

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Backend at `http://localhost:8000`. Web frontend at `http://localhost:5173` (after `cd web && npm run dev`).

### Docker Deployment

```bash
cp .env.example .env
# Edit .env with your credentials
docker compose up
```

Docker Compose runs migrations automatically before starting the app.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/auth/login` | Start OAuth flow |
| GET | `/api/v1/auth/callback` | OAuth callback |
| GET | `/api/v1/auth/status` | Check auth status |
| DELETE | `/api/v1/auth/logout` | Revoke tokens |
| GET | `/api/v1/emails` | List emails from Gmail |
| GET | `/api/v1/emails/stats` | Inbox unread/total counts |
| POST | `/api/v1/analysis` | Start analysis (async, 202) |
| GET | `/api/v1/analysis` | List analyses |
| GET | `/api/v1/analysis/{id}` | Get analysis with summary + emails + insights |
| GET | `/api/v1/analysis/{id}/senders` | Get sender groups (optionally by category) |
| POST | `/api/v1/analysis/{id}/apply` | Apply action with filters |
| DELETE | `/api/v1/analysis/{id}` | Delete analysis |

See [docs/api.md](docs/api.md) for full endpoint reference.

## Development

```bash
# Backend tests
uv run pytest tests/ -x -q

# Lint
uv run ruff check .

# Type check (backend)
uv run mypy app/

# Frontend tests
cd web && npm test

# Frontend type check
cd web && npx tsc --noEmit

# Create a migration
uv run alembic revision --autogenerate -m "description"
```

## Project Structure

```
app/
  api/routes/          # FastAPI route handlers (auth, analysis, emails)
  core/                # Config, database, protocols, security, DI
  models/              # SQLAlchemy models (db.py) + Pydantic schemas (schemas.py)
  repositories/        # Data access layer
  services/            # Business logic (analysis, classification, gmail, auth)
web/
  src/
    api/               # Typed fetch client + TS interfaces
    components/        # Layout, ActionBar, AnalysisProgress, EmailDetailModal, InsightsTab
    context/           # AuthContext (JWT in localStorage)
    hooks/             # useAuth, usePolling
    pages/             # LoginPage, CallbackPage, DashboardPage, AnalysisPage
    styles/            # CSS variables, global styles, animations
    test/              # Test setup, fixtures, render utils
tui/
  screens/             # Textual screens (login, dashboard, analysis, email detail)
  styles/              # Textual CSS
  app.py               # Main Textual App
  client.py            # Typed async httpx API client
  models.py            # Pydantic models (mirrors backend schemas)
  config.py            # TUI configuration
tests/                 # Pytest test suite (includes tests/tui/)
alembic/               # Database migrations
docs/                  # API reference, architecture, frontend guide
scripts/               # Deployment + E2E test scripts
```

## License

MIT

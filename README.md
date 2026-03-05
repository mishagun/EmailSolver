# EmailSolver

Gmail inbox analyzer and cleaner with AI-powered email classification. Uses a two-pass AI system to classify emails, recommend actions per category, and apply them via the Gmail API.

## Features

- **Two-pass AI classification** -- Pass 1 classifies emails into dynamic categories (base + custom). Pass 2 verifies categories, merges duplicates, and recommends actions.
- **Dynamic categories** -- Base set (primary, promotions, social, updates, spam, newsletters, receipts) plus user-provided custom categories. AI can create new ones on the fly.
- **Per-category action recommendations** -- AI recommends actions per category (e.g., promotions -> mark_read, move_to_category). Frontend shows these as buttons.
- **Summary view** -- GET /analysis/{id} returns category counts + recommended actions alongside the email list.
- **Flexible action application** -- Apply actions filtered by category, sender domain, or specific email IDs.
- **Auto-apply mode** -- Optionally apply the top recommended action per category automatically.

## Tech Stack

- **Backend:** FastAPI, Python 3.13+, async/await
- **Database:** PostgreSQL + SQLAlchemy 2.0 (async)
- **AI:** Anthropic Claude (Haiku) via official SDK
- **Auth:** Google OAuth 2.0 with JWT sessions
- **Email:** Gmail API (read, modify, label management)
- **Migrations:** Alembic
- **Security:** Fernet symmetric encryption for tokens

## Self-Hosting Guide

EmailSolver is designed to run locally — your email data stays on your machine and goes directly to the AI provider you configure. No central server involved.

### Prerequisites

- Python 3.13+ (or Docker)
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for PostgreSQL, or bring your own)
- Google Cloud project (free) — for Gmail API access
- Anthropic API key — for email classification

### Step 1: Google Cloud Setup

You need OAuth credentials so EmailSolver can read your Gmail.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a new project
2. Enable the **Gmail API**: APIs & Services > Library > search "Gmail API" > Enable
3. Configure the **OAuth consent screen**: APIs & Services > OAuth consent screen
   - Choose "External" user type
   - Fill in app name (e.g., "EmailSolver") and your email
   - Add scopes: `gmail.readonly`, `gmail.modify`, `gmail.labels`
   - Add your Google account as a test user (required while app is in "Testing" status)
4. Create **OAuth credentials**: APIs & Services > Credentials > Create Credentials > OAuth client ID
   - Application type: "Web application"
   - Authorized redirect URIs: `http://localhost:8000/api/v1/auth/callback`
   - Copy the **Client ID** and **Client Secret**

### Step 2: Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com/) and create an account
2. Go to API Keys > Create Key
3. Copy the key — you'll need it for `.env`

### Step 3: Install and Configure

```bash
# Clone and install
git clone https://github.com/mishagun/EmailSolver.git
cd EmailSolver
uv sync --dev

# Start PostgreSQL
docker compose up -d postgres

# Configure environment
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Database (default works with the docker compose postgres)
DATABASE_URL=postgresql+asyncpg://emailsolver:emailsolver@localhost:5432/emailsolver

# Generate a random JWT secret (e.g.: openssl rand -hex 32)
JWT_SECRET_KEY=<your-random-secret>

# Google OAuth (from Step 1)
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback

# Generate a Fernet key:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=<your-fernet-key>

# Anthropic (from Step 2)
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 4: Run

```bash
# Run database migrations
uv run alembic upgrade head

# Start the server
uv run uvicorn app.main:app --reload --port 8000
```

The server is now running at `http://localhost:8000`. Open `http://localhost:8000/api/v1/auth/login` in your browser to authenticate with Google.

### Docker Deployment (Alternative)

Instead of steps 3-4, you can run everything in Docker:

```bash
cp .env.example .env
# Edit .env with your credentials (same as above)

# Full deployment (builds, migrates, starts)
bash scripts/deploy.sh

# Or manually
docker compose up
```

Docker Compose runs a one-shot `migrations` service before starting the app.

### Privacy Note

When you self-host EmailSolver, your email data flows directly from your machine to the Anthropic API for classification. Only email metadata (sender, subject, snippet) is sent — not full email bodies. No data is stored on any third-party server. Classification results are stored in your local PostgreSQL database and automatically expire after 7 days (configurable via `CLASSIFIED_EMAIL_TTL_DAYS`).

## Terminal UI (TUI)

A full terminal interface for EmailSolver, built with [Textual](https://textual.textualize.io/).

```bash
# Install TUI dependencies
uv pip install -e ".[tui]"

# Run the TUI (backend must be running)
uv run python -m tui
# or
uv run emailsolver-tui
```

**Flow:** Login (paste JWT from browser OAuth) → Dashboard (inbox stats, analyses) → Create Analysis (watch progress) → Browse categories/emails → Apply actions.

**Configuration** via environment variables (prefix `EMAILSOLVER_TUI_`):
| Variable | Default | Description |
|----------|---------|-------------|
| `EMAILSOLVER_TUI_BASE_URL` | `http://localhost:8000` | Backend API URL |
| `EMAILSOLVER_TUI_POLL_INTERVAL_SECONDS` | `2.0` | Analysis polling interval |

Token is persisted at `~/.emailsolver/token`.

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/auth/login` | Start OAuth flow |
| GET | `/api/v1/auth/callback` | OAuth callback |
| GET | `/api/v1/auth/status` | Check auth status |
| POST | `/api/v1/auth/logout` | Revoke tokens |
| GET | `/api/v1/emails` | List emails from Gmail |
| GET | `/api/v1/emails/stats` | Email counts |
| POST | `/api/v1/analysis` | Start analysis (async, 202) |
| GET | `/api/v1/analysis` | List analyses |
| GET | `/api/v1/analysis/{id}` | Get analysis with summary + emails |
| POST | `/api/v1/analysis/{id}/apply` | Apply action with filters |
| DELETE | `/api/v1/analysis/{id}` | Delete analysis |

See [docs/api.md](docs/api.md) for full endpoint reference with request/response examples.

## Documentation

- [API Reference](docs/api.md) -- Full endpoint documentation
- [Architecture](docs/architecture.md) -- Business logic, two-pass AI flow, data model
- [Frontend Guide](docs/frontend-guide.md) -- UI integration guide with code examples

## Development

```bash
# Run tests (backend)
uv run pytest tests/ -v

# Run tests (TUI)
uv run pytest tests/tui/ -v

# Lint
uv run ruff check app/ tui/ tests/

# Type check
uv run mypy app/

# Create a migration
uv run alembic revision --autogenerate -m "description"
```

## Project Structure

```
app/
  api/routes/       # FastAPI route handlers
  core/             # Config, database, protocols, security, DI
  models/           # SQLAlchemy models + Pydantic schemas
  repositories/     # Data access layer
  services/         # Business logic (analysis, classification, Gmail, auth)
tui/
  screens/          # Textual screens (login, dashboard, analysis, email detail)
  styles/           # Textual CSS
  app.py            # Main Textual App
  client.py         # Typed async API client
  models.py         # Pydantic models (mirrors backend schemas)
  config.py         # TUI configuration
tests/              # Pytest test suite (includes tests/tui/)
alembic/            # Database migrations
docs/               # API reference, architecture, frontend guide
```

## License

MIT

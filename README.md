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

## Quick Start

### Prerequisites

- Python 3.13+
- PostgreSQL 16+
- [uv](https://docs.astral.sh/uv/) package manager
- Google Cloud project with Gmail API enabled
- Anthropic API key

### Setup

```bash
# Clone and install
git clone https://github.com/mishagun/EmailSolver.git
cd EmailSolver
uv sync --dev

# Start PostgreSQL
docker compose up -d postgres

# Configure environment
cp .env.example .env
# Edit .env with your credentials (see Configuration below)

# Run migrations
uv run alembic upgrade head

# Start the server
uv run uvicorn app.main:app --reload --port 8000
```

### Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Random secret for JWT signing |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL |
| `FERNET_KEY` | Encryption key (generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `ANTHROPIC_MODEL` | Claude model ID (default: `claude-haiku-4-5-20251001`) |

### Docker

```bash
# Full deployment (builds, migrates, starts)
bash scripts/deploy.sh

# Or manually
docker compose up
```

Docker Compose runs a one-shot `migrations` service before starting the app. The app depends on `migrations: service_completed_successfully`.

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
# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check app/ tests/

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
tests/              # Pytest test suite
alembic/            # Database migrations
docs/               # API reference, architecture, frontend guide
```

## License

MIT

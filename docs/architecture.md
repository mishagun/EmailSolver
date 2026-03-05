# Architecture & Business Logic

## Service Dependencies

```
AnalysisService
  ├── EmailService (Gmail API)
  ├── ClassificationService (Claude AI)
  ├── SecurityService (encryption/JWT)
  ├── ClassifiedEmailRepository (DB)
  └── AnalysisRepository (DB, created per-run)
```

All services are injected via FastAPI dependency injection (`app/core/dependencies.py`). The `AnalysisService` creates its own `AnalysisRepository` per background task since the task outlives the request's DB session.

---

## Analysis Lifecycle

```
pending → processing → completed
                    └→ failed
```

- **pending** -- analysis created, background task not yet started
- **processing** -- fetching emails and classifying (progress tracked via `processed_emails`)
- **completed** -- classification + verification done, results available
- **failed** -- unrecoverable error; `error_message` contains details

---

## Two-Pass AI Classification

### Pass 1: Classification

Emails are classified in batches of 20 using Claude AI, with up to 3 batches running concurrently (`CLASSIFICATION_CONCURRENCY = 3`). API calls use tenacity retry with exponential backoff for transient errors (429 rate limit, 529 overloaded).

**Dynamic categories:** The system starts with base categories (`primary`, `promotions`, `social`, `updates`, `spam`, `newsletters`, `receipts`) plus any user-provided `custom_categories`. If the AI creates a new category for batch N, it becomes available for batch N+1.

```
Batch 1: existing_categories = [primary, promotions, social, ...]
  → AI returns "receipts" for some emails
Batch 2: existing_categories = [primary, promotions, ..., receipts]
  → AI can now assign "receipts" to more emails
```

The classification prompt asks the AI to return:
- `category` -- from available categories or a new snake_case name
- `importance` -- 1-5 scale
- `sender_type` -- human, automated, marketing, transactional
- `confidence` -- 0.0-1.0

### Pass 2: Verification

After all batches are classified, a second AI call reviews the categories:

1. **Merge detection** -- identifies duplicate/overlapping categories (e.g., `promo` and `promotions`)
2. **Action recommendations** -- for each final category, recommends actions from: `keep`, `mark_read`, `move_to_category`, `mark_spam`, `unsubscribe`

The verification call receives 3-5 sample emails per category (subject + sender) to make informed decisions.

**Merge application:** When merges are detected, `bulk_update_category` renames all emails from the source category to the target category in a single DB update.

**Storage:** The `category_actions` dict is stored as JSON on the `Analysis` record:
```json
{
  "promotions": ["mark_read", "move_to_category"],
  "spam": ["mark_spam"],
  "primary": ["keep"],
  "receipts": ["mark_read"]
}
```

---

## Action System

Actions map to Gmail API operations:

| Action | Gmail API call |
|--------|---------------|
| `keep` | No-op |
| `move_to_category` | `get_or_create_label(category_name)` then `modify_messages(add_labels=[label_id])` |
| `mark_read` | `modify_messages(remove_labels=[UNREAD])` |
| `mark_spam` | `modify_messages(add_labels=[SPAM], remove_labels=[INBOX])` |
| `unsubscribe` | RFC 8058 HTTP POST if `unsubscribe_post_header` + HTTP URL present → archive (remove INBOX); fallback → `modify_messages(add_labels=[SPAM], remove_labels=[INBOX])` |

**Gmail user labels for `move_to_category`:** Instead of using Gmail's system category labels (CATEGORY_PROMOTIONS, etc.), the system creates Gmail user labels matching the category name (e.g., `promotions`, `receipts`, `newsletters`). Labels are created on first use via `get_or_create_label` and reused on subsequent calls.

**Multiple actions per email:** Actions are not mutually exclusive. An email can be both categorized (`move_to_category`) and marked as read (`mark_read`). The `action_taken` field tracks the last action applied but does not block subsequent actions.

Actions are applied in bulk (`bulk_update_action_taken`) rather than per-email for efficiency.

---

## Auto-Apply

When `auto_apply=true` on analysis creation:

1. After Pass 2 completes, the service groups emails by category
2. For each category, picks the **first** recommended action from `category_actions`
3. Applies that action to all emails in the category
4. Skips categories where the first action is `keep`

---

## Data Model

### Analysis

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `user_id` | int | FK to users |
| `status` | string | pending/processing/completed/failed |
| `query` | string | Gmail search query used |
| `total_emails` | int | Total emails found |
| `processed_emails` | int | Emails classified so far |
| `category_actions` | JSON | Per-category recommended actions from Pass 2 |
| `error_message` | text | Error details if failed |
| `created_at` | datetime | When analysis was created |
| `completed_at` | datetime | When analysis finished |

### ClassifiedEmail

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `analysis_id` | int | FK to analyses (CASCADE delete) |
| `gmail_message_id` | string | Gmail message ID |
| `gmail_thread_id` | string | Gmail thread ID |
| `sender` | string | Full sender string |
| `sender_domain` | string | Extracted domain |
| `subject` | string | Email subject |
| `snippet` | text | Email preview text |
| `received_at` | datetime | When email was received |
| `category` | string | AI-assigned category |
| `importance` | int | 1-5 scale |
| `sender_type` | string | human/automated/marketing/transactional |
| `confidence` | float | 0.0-1.0 classification confidence |
| `has_unsubscribe` | bool | Whether email has unsubscribe header |
| `unsubscribe_header` | text | Raw `List-Unsubscribe` header value |
| `unsubscribe_post_header` | text | Raw `List-Unsubscribe-Post` header value |
| `action_taken` | string | Action applied (null if none) |
| `expires_at` | datetime | TTL for cleanup (default: 7 days) |

Indexes: `category`, `sender_domain`, `expires_at`, `analysis_id`.

---

## Security

### OAuth Flow

| Mechanism | Implementation |
|-----------|---------------|
| State nonce | `_state_store: dict[str, tuple[str, float]]` in `auth_service.py`, guarded by `threading.Lock` |
| TTL | 10 minutes from `start_authorization`; expired entries are rejected |
| Replay protection | `exchange_code()` pops the nonce — a second use of the same state returns 400 |
| PKCE | `code_verifier` generated in `start_authorization`, stored server-side, never in the URL |
| Port validation | `callback_port` must be in `range(1024, 65536)` at both `/login` and `/callback`; privileged and zero ports return 400 |

### Token Encryption and JWT

- **Google tokens** (access + refresh) are encrypted with Fernet before storage in the database.
- **Session JWTs** are signed with HMAC-SHA (HS256/384/512). Every token carries a `jti` UUID claim.
- JWT expiry is enforced on every `decode_jwt` call. `revoke_jwt` adds the `jti` to an in-memory denylist with TTL equal to the remaining token lifetime, so revoked tokens are rejected until they would have expired naturally.
- The denylist is single-process. Multi-process deployments need a shared store (e.g., Redis).

### Config Validation

Validated at startup via Pydantic `field_validator` in `app/core/config.py`:

| Field | Rule |
|-------|------|
| `jwt_secret_key` | >= 32 characters |
| `fernet_key` | non-empty |
| `jwt_algorithm` | one of `HS256`, `HS384`, `HS512` |

The app refuses to start if any rule is violated — weak defaults cannot reach production.

### TUI Token Storage

`tui/app.py` `save_token()` creates `~/.emailsolver/` with `mode=0o700` and writes the token file with `chmod(0o600)`. This prevents world-readable JWTs on shared systems.

---

## Repository Layer

Repositories use SQLAlchemy async with two patterns:
- **Session-injected** (`AnalysisRepository`): receives an `AsyncSession` from the request scope
- **Session-maker** (`ClassifiedEmailRepository`): creates sessions internally, used by background tasks

The `AnalysisRepository` supports both patterns -- `session` for request-scope operations, `session_maker` for background task operations (`update_status`, `update_category_actions`).

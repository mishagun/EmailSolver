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
| `unsubscribe` | `modify_messages(add_labels=[SPAM], remove_labels=[INBOX])` |

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
| `action_taken` | string | Action applied (null if none) |
| `expires_at` | datetime | TTL for cleanup (default: 7 days) |

Indexes: `category`, `sender_domain`, `expires_at`, `analysis_id`.

---

## Repository Layer

Repositories use SQLAlchemy async with two patterns:
- **Session-injected** (`AnalysisRepository`): receives an `AsyncSession` from the request scope
- **Session-maker** (`ClassifiedEmailRepository`): creates sessions internally, used by background tasks

The `AnalysisRepository` supports both patterns -- `session` for request-scope operations, `session_maker` for background task operations (`update_status`, `update_category_actions`).

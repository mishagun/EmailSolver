# API Endpoint Reference

All endpoints are prefixed with `/api/v1` unless noted otherwise. Protected endpoints require a `Bearer` token in the `Authorization` header.

---

## Health

### `GET /health`

Returns application health status.

**Auth:** None

**Response 200:**
```json
{
  "status": "healthy",
  "environment": "development"
}
```

---

## Auth

### `GET /api/v1/auth/login`

Starts the Google OAuth 2.0 flow. Redirects the user to Google's consent page.

**Auth:** None

**Response:** `302 Redirect` to Google OAuth URL.

---

### `GET /api/v1/auth/callback`

Handles the OAuth callback from Google. Creates or updates the user, encrypts tokens, and returns a JWT.

**Auth:** None

**Query params:**
- `code` (required) -- authorization code from Google
- `state` (required) -- CSRF + PKCE state

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

---

### `GET /api/v1/auth/status`

Returns the authenticated user's info.

**Auth:** Required

**Response 200:**
```json
{
  "authenticated": true,
  "email": "user@gmail.com",
  "display_name": "User Name"
}
```

---

### `POST /api/v1/auth/logout`

Revokes the user's Google tokens and clears stored credentials.

**Auth:** Required

**Response 200:**
```json
{ "message": "Logged out successfully" }
```

---

## Emails

### `GET /api/v1/emails`

Lists emails from Gmail matching a search query.

**Auth:** Required

**Query params:**
- `query` (optional, default `"is:unread"`) -- Gmail search query
- `max_results` (optional, default `500`) -- max emails to return

**Response 200:**
```json
{
  "emails": [
    {
      "gmail_message_id": "abc123",
      "gmail_thread_id": "thread-1",
      "sender": "alice@example.com",
      "sender_domain": "example.com",
      "subject": "Meeting tomorrow",
      "snippet": "Hey, are we still on for...",
      "received_at": "2026-03-01T10:00:00Z",
      "has_unsubscribe": false
    }
  ],
  "total": 1,
  "query": "is:unread"
}
```

---

### `GET /api/v1/emails/stats`

Returns email count stats for the authenticated user.

**Auth:** Required

**Response 200:**
```json
{
  "unread_count": 42,
  "total_count": 1500
}
```

---

## Analysis

### `POST /api/v1/analysis`

Starts a new email analysis job. Returns immediately (202) while processing runs in the background.

**Auth:** Required

**Request body:**
```json
{
  "query": "is:unread",
  "max_emails": 100,
  "auto_apply": false,
  "custom_categories": ["receipts", "travel"]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | `"is:unread"` | Gmail search query |
| `max_emails` | int | `100` | Maximum emails to classify |
| `auto_apply` | bool | `false` | Auto-apply recommended actions after classification |
| `custom_categories` | string[] or null | `null` | Additional categories for the AI to use |

**Response 202:**
```json
{
  "id": 1,
  "status": "pending",
  "query": "is:unread",
  "total_emails": null,
  "processed_emails": null,
  "error_message": null,
  "created_at": "2026-03-03T12:00:00Z",
  "completed_at": null,
  "summary": null,
  "classified_emails": null
}
```

---

### `GET /api/v1/analysis`

Lists all analyses for the authenticated user, ordered by creation date (newest first).

**Auth:** Required

**Response 200:**
```json
{
  "analyses": [
    {
      "id": 1,
      "status": "completed",
      "query": "is:unread",
      "total_emails": 50,
      "processed_emails": 50,
      "error_message": null,
      "created_at": "2026-03-03T12:00:00Z",
      "completed_at": "2026-03-03T12:01:30Z",
      "summary": null,
      "classified_emails": null
    }
  ],
  "total": 1
}
```

Note: List endpoint does not include `summary` or `classified_emails`. Use the detail endpoint for those.

---

### `GET /api/v1/analysis/{id}`

Returns a single analysis with its classified emails and summary.

**Auth:** Required

**Response 200:**
```json
{
  "id": 1,
  "status": "completed",
  "query": "is:unread",
  "total_emails": 50,
  "processed_emails": 50,
  "error_message": null,
  "created_at": "2026-03-03T12:00:00Z",
  "completed_at": "2026-03-03T12:01:30Z",
  "summary": [
    {
      "category": "promotions",
      "count": 30,
      "recommended_actions": ["mark_read", "move_to_category", "unsubscribe"]
    },
    {
      "category": "primary",
      "count": 10,
      "recommended_actions": ["keep"]
    },
    {
      "category": "spam",
      "count": 5,
      "recommended_actions": ["mark_spam"]
    },
    {
      "category": "receipts",
      "count": 5,
      "recommended_actions": ["mark_read"]
    }
  ],
  "classified_emails": [
    {
      "id": 1,
      "gmail_message_id": "abc123",
      "gmail_thread_id": "thread-1",
      "sender": "shop@store.com",
      "sender_domain": "store.com",
      "subject": "50% Off Sale!",
      "snippet": "Don't miss our biggest...",
      "received_at": "2026-03-01T10:00:00Z",
      "category": "promotions",
      "importance": 2,
      "sender_type": "marketing",
      "confidence": 0.95,
      "has_unsubscribe": true,
      "action_taken": null
    }
  ]
}
```

**Summary** is sorted by count (descending). `recommended_actions` come from the AI verification pass and are stored on the analysis as `category_actions`.

**Error 404:** Analysis not found or belongs to another user.

---

### `POST /api/v1/analysis/{id}/apply`

Applies an explicit action to a filtered set of emails within an analysis.

**Auth:** Required

**Request body:**
```json
{
  "action": "mark_read",
  "category": "promotions",
  "sender_domain": null,
  "email_ids": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | ActionType | yes | Action to apply (see below) |
| `category` | string or null | no | Filter: apply only to emails in this category |
| `sender_domain` | string or null | no | Filter: apply only to emails from this domain |
| `email_ids` | int[] or null | no | Filter: apply only to these specific email IDs |

If no filter is provided, the action applies to all emails in the analysis.

Filter priority (first match wins):
1. `email_ids` -- specific emails
2. `category` -- all emails in the category
3. `sender_domain` -- all emails from the domain
4. none -- all emails

**ActionType values:**
| Value | Gmail effect |
|-------|-------------|
| `keep` | No-op |
| `move_to_category` | Add Gmail category label, remove INBOX |
| `mark_read` | Remove UNREAD label |
| `mark_spam` | Add SPAM label, remove INBOX |
| `unsubscribe` | Add SPAM label, remove INBOX |

**Response 200:**
```json
{ "message": "Actions applied successfully" }
```

**Error 400:** Analysis is not in `completed` status.
**Error 404:** Analysis not found.
**Error 422:** Invalid `action` value.

---

### `DELETE /api/v1/analysis/{id}`

Deletes an analysis and all its classified emails.

**Auth:** Required

**Response 200:**
```json
{ "message": "Analysis and classified emails deleted" }
```

**Error 404:** Analysis not found.

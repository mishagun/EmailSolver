# Frontend Integration Guide

## Typical User Flow

```
1. Login (OAuth)
2. Create analysis → get analysis ID
3. Poll for completion
4. Show summary + email list
5. User picks actions per category
6. Apply actions
```

---

## 1. Authentication

```
GET /api/v1/auth/login → redirect to Google
GET /api/v1/auth/callback?code=...&state=... → { access_token, token_type }
```

Store the JWT `access_token` and include it in all subsequent requests:
```
Authorization: Bearer <token>
```

---

## 2. Create Analysis

```http
POST /api/v1/analysis
Content-Type: application/json

{
  "query": "is:unread",
  "max_emails": 100,
  "custom_categories": ["receipts", "travel"]
}
```

Returns `202 Accepted` with the analysis object (status: `"pending"`).

Save the `id` for polling.

---

## 3. Poll for Completion

```http
GET /api/v1/analysis/{id}
```

Poll every 2-3 seconds while `status` is `"pending"` or `"processing"`.

During processing, use `processed_emails` / `total_emails` to show a progress bar:

```
Progress: 40 / 100 emails classified
```

Stop polling when status is `"completed"` or `"failed"`.

---

## 4. Display Summary

When `status === "completed"`, the response includes a `summary` array:

```json
"summary": [
  { "category": "promotions", "count": 30, "recommended_actions": ["mark_read", "move_to_category"] },
  { "category": "primary", "count": 15, "recommended_actions": ["keep"] },
  { "category": "spam", "count": 8, "recommended_actions": ["mark_spam"] },
  { "category": "receipts", "count": 5, "recommended_actions": ["mark_read"] }
]
```

Summary is sorted by count (descending). Render as:

```
+-------------------------------------------+
| promotions (30)    [Mark Read] [Move]     |
| primary (15)       [Keep]                 |
| spam (8)           [Mark Spam]            |
| receipts (5)       [Mark Read]            |
+-------------------------------------------+
```

Each action button in `recommended_actions` maps to an `ActionType`:
- `keep` -- no action needed (gray/disabled button)
- `mark_read` -- marks emails as read
- `move_to_category` -- moves to Gmail category tab
- `mark_spam` -- marks as spam
- `unsubscribe` -- marks as spam (for newsletters with unsubscribe headers)

---

## 5. Apply Actions

When the user clicks an action button for a category:

```http
POST /api/v1/analysis/{id}/apply
Content-Type: application/json

{
  "action": "mark_read",
  "category": "promotions"
}
```

### Filter Options

Apply to a specific category:
```json
{ "action": "mark_read", "category": "promotions" }
```

Apply to a specific sender domain:
```json
{ "action": "mark_spam", "sender_domain": "spam-sender.com" }
```

Apply to specific emails (e.g., user-selected checkboxes):
```json
{ "action": "mark_read", "email_ids": [1, 5, 12] }
```

Apply to all emails:
```json
{ "action": "mark_read" }
```

### Valid Actions

`keep`, `move_to_category`, `mark_read`, `mark_spam`, `unsubscribe`

Invalid actions return `422 Unprocessable Entity`.

---

## 6. Email List

The `classified_emails` array contains all classified emails:

```json
{
  "id": 1,
  "gmail_message_id": "abc123",
  "sender": "shop@store.com",
  "sender_domain": "store.com",
  "subject": "50% Off Sale!",
  "snippet": "Don't miss our biggest...",
  "category": "promotions",
  "importance": 2,
  "sender_type": "marketing",
  "confidence": 0.95,
  "has_unsubscribe": true,
  "action_taken": null
}
```

- Filter/group by `category` to show per-category lists
- Sort by `importance` (5 = most important) within each category
- Show `confidence` as a visual indicator (color/badge)
- `action_taken` is non-null after an action has been applied
- `sender_type` can be used for visual grouping (human emails vs automated)

---

## Error Handling

| Status | Meaning |
|--------|---------|
| 401 | JWT expired or invalid -- redirect to login |
| 400 | Analysis not completed yet (for `/apply`) |
| 404 | Analysis not found or belongs to another user |
| 422 | Invalid request body (bad action type, missing fields) |

---

## Example: Full Workflow

```javascript
// 1. Create analysis
const { id } = await fetch('/api/v1/analysis', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'is:unread', max_emails: 200 })
}).then(r => r.json());

// 2. Poll until complete
let analysis;
do {
  await new Promise(r => setTimeout(r, 2000));
  analysis = await fetch(`/api/v1/analysis/${id}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  }).then(r => r.json());
} while (analysis.status === 'pending' || analysis.status === 'processing');

// 3. Show summary
for (const cat of analysis.summary) {
  console.log(`${cat.category}: ${cat.count} emails`);
  console.log(`  Actions: ${cat.recommended_actions.join(', ')}`);
}

// 4. Apply action to a category
await fetch(`/api/v1/analysis/${id}/apply`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ action: 'mark_read', category: 'promotions' })
});
```

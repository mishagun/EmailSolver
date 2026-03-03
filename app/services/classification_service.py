import json
import logging

from anthropic import AsyncAnthropic

from app.core.protocols import BaseClassificationService
from app.models.schemas import (
    CategoryMerge,
    ClassificationResult,
    EmailMetadata,
    VerificationResult,
)

logger = logging.getLogger(__name__)

BASE_CATEGORIES = ["primary", "promotions", "social", "updates", "spam", "newsletters"]

CLASSIFICATION_SYSTEM_PROMPT = """\
You are an email classification assistant. \
Classify each email into exactly one category.

Available categories (prefer these): {categories}
You may create a new category if none of the above fit. Use lowercase snake_case names.

For each email, provide:
- category: one of the available categories or a new one
- importance: 1-5 (1=lowest, 5=highest)
- sender_type: one of "human", "automated", "marketing", "transactional"
- confidence: 0.0-1.0 (how confident you are in the classification)

Return a JSON array with one object per email, each containing:
{{"gmail_message_id": "...", "category": "...", "importance": N,
"sender_type": "...", "confidence": N.N}}

Return ONLY the JSON array, no other text."""

VERIFICATION_SYSTEM_PROMPT = """Review these email categories and their sample emails.

1. If any categories should be merged (duplicates/overlaps), list merges.
2. For each final category, recommend which actions make sense from:
   keep, mark_read, move_to_category, mark_spam, unsubscribe

Return JSON:
{"merges": [{"from_category": "...", "to_category": "..."}],
 "category_actions": {"category_name": ["action1", "action2"]}}

Return ONLY the JSON object, no other text."""


class ClaudeClassificationService(BaseClassificationService):
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def classify_emails(
        self,
        *,
        emails: list[EmailMetadata],
        existing_categories: list[str] | None = None,
    ) -> list[ClassificationResult]:
        if not emails:
            return []

        categories = existing_categories or BASE_CATEGORIES
        system_prompt = CLASSIFICATION_SYSTEM_PROMPT.format(
            categories=", ".join(categories)
        )

        emails_data = [
            {
                "gmail_message_id": e.gmail_message_id,
                "sender": e.sender,
                "sender_domain": e.sender_domain,
                "subject": e.subject,
                "snippet": e.snippet,
                "has_unsubscribe": e.has_unsubscribe,
            }
            for e in emails
        ]

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Classify these emails:\n{json.dumps(emails_data)}",
                }
            ],
        )

        raw_text = response.content[0].text
        results = json.loads(raw_text)
        return [ClassificationResult(**r) for r in results]

    async def verify_categories(
        self, *, category_samples: dict[str, list[dict]]
    ) -> VerificationResult:
        if not category_samples:
            return VerificationResult(merges=[], category_actions={})

        samples_text = json.dumps(category_samples, indent=2)

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=VERIFICATION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Categories and samples:\n{samples_text}",
                }
            ],
        )

        raw_text = response.content[0].text
        data = json.loads(raw_text)

        merges = [CategoryMerge(**m) for m in data.get("merges", [])]
        category_actions = data.get("category_actions", {})

        return VerificationResult(merges=merges, category_actions=category_actions)

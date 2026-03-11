import json
import logging
import re

from anthropic import APIStatusError, AsyncAnthropic, Timeout
from anthropic.types import Message, TextBlock
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from tenacity import RetryCallState, retry, retry_if_exception, stop_after_attempt

from app.core.protocols import BaseClassificationService
from app.models.schemas import (
    ClassificationResult,
    EmailMetadata,
    VerificationResult,
)

logger = logging.getLogger(__name__)

BASE_CATEGORIES = ["primary", "promotions", "social", "updates", "spam", "newsletters", "receipts"]

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

INSIGHTS_SYSTEM_PROMPT = """\
You are an email analyst. Given a summary of someone's email categories and samples, \
generate 8-10 short dry observations about their inbox.

Focus on how much of their email is junk — newsletters they never read, promotions they ignore, \
automated noise drowning out the few emails that actually matter. Be matter-of-fact, not clever. \
Point out the ratio of trash to real mail. Examples of tone:
- "93% of your inbox is stuff no human wrote"
- "you have 4 actual emails buried under 200 promotions"
- "linkedin alone accounts for a third of your unread"

Return a JSON array of strings. Each string should be a single short sentence (under 80 chars).
Return ONLY the JSON array, no other text."""

VERIFICATION_SYSTEM_PROMPT = """Review these email categories and their sample emails.

For each category, recommend which actions make sense from:
  mark_read, move_to_category, mark_spam, unsubscribe, keep
  The user's main goal is inbox zero — reducing unread count. \
  Prefer mark_read as the first action for most categories. \
  Only use keep alone for categories that need user attention (e.g., primary, important).

Return JSON:
{{"category_actions": {{"category_name": ["action1", "action2"]}}}}

Return ONLY the JSON object, no other text."""


def _extract_json(response: Message) -> str:
    logger.debug(
        "API response: stop_reason=%s, content_blocks=%d, usage=%s",
        response.stop_reason,
        len(response.content),
        response.usage,
    )
    for i, block in enumerate(response.content):
        logger.debug("Block %d: type=%s", i, block.type)
        if isinstance(block, TextBlock):
            logger.debug("Block %d text (first 500 chars): %s", i, block.text[:500])
            if block.text:
                text = block.text.strip()
                fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
                if fence_match:
                    return fence_match.group(1).strip()
                return text
    block_types = [b.type for b in response.content]
    raise ValueError(
        f"No text content in API response "
        f"(stop_reason={response.stop_reason}, blocks={block_types})"
    )


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, APIStatusError) and exc.status_code in {429, 529}


def _wait_for_rate_limit(retry_state: RetryCallState) -> float:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        retry_after = exc.response.headers.get("retry-after")
        if retry_after:
            wait_seconds = float(retry_after)
            logger.info(
                "Rate limited (attempt %d), waiting %.1fs (retry-after header)",
                retry_state.attempt_number, wait_seconds,
            )
            return wait_seconds
    wait_seconds = min(2.0 ** retry_state.attempt_number, 60.0)
    logger.warning(
        "Anthropic API error (attempt %d), retrying in %.1fs: %s",
        retry_state.attempt_number, wait_seconds, exc,
    )
    return wait_seconds


class ClaudeClassificationService(BaseClassificationService):
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(
            api_key=api_key,
            max_retries=0,
            timeout=Timeout(timeout=120.0, connect=10.0),
        )
        self._model = model

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(6),
        wait=_wait_for_rate_limit,
        reraise=True,
    )
    async def _create_message(self, *, system: str, content: str) -> Message:
        return await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": content}],
        )

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

        logger.info("Classifying %d emails with model=%s", len(emails), self._model)

        response = await self._create_message(
            system=system_prompt,
            content=f"Classify these emails:\n{json.dumps(emails_data)}",
        )

        if response.stop_reason != "end_turn":
            logger.warning(
                "Classification response truncated: stop_reason=%s (model=%s, %d emails)",
                response.stop_reason, self._model, len(emails),
            )

        raw_text = _extract_json(response)
        logger.debug("Classification raw JSON (first 500 chars): %s", raw_text[:500])
        results = json.loads(raw_text)
        logger.info(
            "Classification returned %d results for %d emails",
            len(results), len(emails),
        )
        return [ClassificationResult(**r) for r in results]

    async def submit_batch_classification(
        self,
        *,
        email_batches: list[list[EmailMetadata]],
        existing_categories: list[str] | None = None,
    ) -> str:
        categories = existing_categories or BASE_CATEGORIES
        system_prompt = CLASSIFICATION_SYSTEM_PROMPT.format(
            categories=", ".join(categories)
        )

        requests: list[Request] = []
        for batch_idx, batch_emails in enumerate(email_batches):
            emails_data = [
                {
                    "gmail_message_id": e.gmail_message_id,
                    "sender": e.sender,
                    "sender_domain": e.sender_domain,
                    "subject": e.subject,
                    "snippet": e.snippet,
                    "has_unsubscribe": e.has_unsubscribe,
                }
                for e in batch_emails
            ]
            requests.append(
                Request(
                    custom_id=f"batch-{batch_idx}",
                    params=MessageCreateParamsNonStreaming(
                        model=self._model,
                        max_tokens=4096,
                        system=system_prompt,
                        messages=[{
                            "role": "user",
                            "content": f"Classify these emails:\n{json.dumps(emails_data)}",
                        }],
                    ),
                )
            )

        logger.info(
            "Submitting batch classification: %d requests with model=%s",
            len(requests), self._model,
        )
        message_batch = await self._client.messages.batches.create(requests=requests)
        logger.info("Batch created: id=%s", message_batch.id)
        return message_batch.id

    async def check_batch_status(self, *, batch_id: str) -> str:
        batch = await self._client.messages.batches.retrieve(batch_id)
        return batch.processing_status

    async def retrieve_batch_results(
        self, *, batch_id: str
    ) -> dict[str, list[ClassificationResult]]:
        results: dict[str, list[ClassificationResult]] = {}
        async for result in await self._client.messages.batches.results(batch_id):
            if result.result.type == "succeeded":
                raw_text = _extract_json(result.result.message)
                parsed = json.loads(raw_text)
                results[result.custom_id] = [
                    ClassificationResult(**r) for r in parsed
                ]
            else:
                logger.warning(
                    "Batch result %s: type=%s",
                    result.custom_id, result.result.type,
                )
        return results

    async def generate_insights(
        self,
        category_samples: dict[str, list[dict]],
    ) -> list[str]:
        if not category_samples:
            return []

        samples_text = json.dumps(category_samples, indent=2)

        logger.info("Generating insights for %d categories", len(category_samples))

        response = await self._create_message(
            system=INSIGHTS_SYSTEM_PROMPT,
            content=f"Email categories and samples:\n{samples_text}",
        )

        raw_text = _extract_json(response)
        insights = json.loads(raw_text)
        if not isinstance(insights, list):
            return []
        return [str(i) for i in insights if isinstance(i, str)]

    async def verify_categories(
        self,
        category_samples: dict[str, list[dict]],
    ) -> VerificationResult:
        if not category_samples:
            return VerificationResult(merges=[], category_actions={})

        samples_text = json.dumps(category_samples, indent=2)

        logger.info("Verifying %d categories with model=%s", len(category_samples), self._model)

        response = await self._create_message(
            system=VERIFICATION_SYSTEM_PROMPT,
            content=f"Categories and samples:\n{samples_text}",
        )

        raw_text = _extract_json(response)
        logger.debug("Verification raw JSON (first 500 chars): %s", raw_text[:500])
        data = json.loads(raw_text)

        category_actions = data.get("category_actions", {})

        return VerificationResult(merges=[], category_actions=category_actions)

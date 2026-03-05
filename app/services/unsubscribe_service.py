import re
import logging

import httpx

logger = logging.getLogger(__name__)

_URL_PATTERN = re.compile(r"<(https?://[^>]+)>")


def parse_unsubscribe_urls(*, header: str) -> list[str]:
    return _URL_PATTERN.findall(header)


async def attempt_http_unsubscribe(*, url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                content="List-Unsubscribe=One-Click-Unsubscribe",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            return response.status_code < 300
    except Exception:
        logger.warning("HTTP unsubscribe failed for %s", url, exc_info=True)
        return False

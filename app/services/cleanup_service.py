import asyncio

from app.core.protocols import BaseClassifiedEmailRepository


class CleanupService:
    def __init__(self, *, repository: BaseClassifiedEmailRepository) -> None:
        self._repository = repository

    async def cleanup_expired_emails(self) -> None:
        await self._repository.delete_expired()

    async def _periodic_cleanup(self, *, interval_seconds: int) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            await self.cleanup_expired_emails()

    def start_periodic_cleanup(
        self, *, interval_seconds: int = 3600
    ) -> asyncio.Task:
        return asyncio.create_task(
            self._periodic_cleanup(interval_seconds=interval_seconds)
        )

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analysis, auth, emails
from app.core.config import config
from app.core.database import async_session_maker
from app.models.schemas import HealthResponse
from app.repositories.classified_email_repository import SQLAlchemyClassifiedEmailRepository
from app.services.cleanup_service import CleanupService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    repository = SQLAlchemyClassifiedEmailRepository(session_maker=async_session_maker)
    cleanup_service = CleanupService(repository=repository)
    await cleanup_service.cleanup_expired_emails()
    cleanup_task = cleanup_service.start_periodic_cleanup(interval_seconds=3600)
    yield
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup_task


def create_app() -> FastAPI:
    application = FastAPI(
        title="EmailSolver",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    application.include_router(emails.router, prefix="/api/v1/emails", tags=["emails"])
    application.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", environment=config.app_env)

    return application


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
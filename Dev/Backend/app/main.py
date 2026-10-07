"""FastAPI application and composition root.

Run from Dev/Backend:  uvicorn app.main:app --reload --port 5000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.controllers import health
from app.controllers.conversation.endpoints import router as conversation_router


def create_app() -> FastAPI:
    app = FastAPI(title="Voice Assistant for Older Adults", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # needed for the HttpOnly refresh-token cookie
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Kept at /api/health so the existing frontend keeps working.
    # Feature routers go under /api/v1.
    app.include_router(health.router, prefix="/api")
    app.include_router(conversation_router, prefix="/api/v1")

    return app


app = create_app()

# Public application entry point for other servers and imports.
__all__ = ["app", "create_app"]
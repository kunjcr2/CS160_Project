"""FastAPI application and composition root.

Run from Dev/Backend:  uvicorn app.main:app --reload --port 5000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.controllers import actions, appointments, health, notifications
from app.workers import reminders


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_worker = reminders.start_in_background() if settings.run_reminder_worker else None
    yield
    if stop_worker:
        stop_worker.set()


def create_app() -> FastAPI:
    app = FastAPI(title="Voice Assistant for Older Adults", version="0.1.0", lifespan=lifespan)

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
    app.include_router(actions.router, prefix="/api/v1")
    app.include_router(appointments.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")

    return app


app = create_app()

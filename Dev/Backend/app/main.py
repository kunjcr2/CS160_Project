"""FastAPI application and composition root.

Run from Dev/Backend:  uvicorn app.main:app --reload --port 5000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.healthcare.interface import HealthcareProvider
from app.adapters.healthcare.mock import MockHealthcareProvider
from app.config import settings
from app.controllers import auth, consents, health, medications, older_adults, users


def build_healthcare_provider() -> HealthcareProvider:
    """Factory: choose the doctor's-office system from settings (plan §4).

    Only the mock exists today. A real FHIR client would be chosen here later,
    and no other code would change.
    """
    return MockHealthcareProvider(
        latency_ms=settings.mock_provider_latency_ms,
        failure_rate=settings.mock_provider_failure_rate,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Voice Assistant for Older Adults", version="0.1.0")
    # ONE shared doctor's office for all requests, so bookings are remembered.
    app.state.healthcare = build_healthcare_provider()

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
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(older_adults.router, prefix="/api/v1")
    app.include_router(consents.router, prefix="/api/v1")
    app.include_router(medications.router, prefix="/api/v1")

    return app


app = create_app()

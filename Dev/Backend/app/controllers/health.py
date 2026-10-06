"""Health check (migrated from the old Flask app; same path and response)."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "backend"}

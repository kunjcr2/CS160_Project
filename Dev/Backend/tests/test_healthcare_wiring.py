"""The app builds ONE doctor's office from settings and gives it to endpoints."""

from fastapi.testclient import TestClient

from app.adapters.healthcare.interface import ProviderUnavailableError
from app.adapters.healthcare.mock import MockHealthcareProvider
from app.config import settings
from app.controllers.dependencies import Healthcare
from app.main import create_app


def test_app_uses_the_mock_office():
    app = create_app()
    assert isinstance(app.state.healthcare, MockHealthcareProvider)


def test_settings_are_passed_to_the_office(monkeypatch):
    monkeypatch.setattr(settings, "mock_provider_failure_rate", 1.0)  # always fail
    app = create_app()
    try:
        app.state.healthcare.list_practitioners()
        raise AssertionError("expected ProviderUnavailableError")
    except ProviderUnavailableError:
        pass


def test_every_request_gets_the_same_office():
    app = create_app()

    @app.get("/test-office")  # a tiny endpoint, only for this test
    def office_id(office: Healthcare):
        return {"id": id(office)}

    client = TestClient(app)
    first = client.get("/test-office").json()["id"]
    second = client.get("/test-office").json()["id"]
    assert first == second == id(app.state.healthcare)

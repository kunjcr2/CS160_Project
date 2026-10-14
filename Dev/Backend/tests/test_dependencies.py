"""The temporary X-User-Id stand-in for auth is off unless DEV_USER_HEADER=true."""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_dev_user_header_is_ignored_by_default(make_user, monkeypatch):
    monkeypatch.setattr(settings, "dev_user_header", False)
    user = make_user()
    response = TestClient(app).get("/api/v1/actions/pending", headers={"X-User-Id": str(user.id)})
    assert response.status_code == 401


def test_dev_user_header_identifies_the_user_when_enabled(make_user, monkeypatch):
    monkeypatch.setattr(settings, "dev_user_header", True)
    user = make_user()
    client = TestClient(app)

    assert client.get("/api/v1/actions/pending").status_code == 401
    response = client.get("/api/v1/actions/pending", headers={"X-User-Id": str(user.id)})
    assert response.status_code == 200
    assert response.json() == {"action": None}

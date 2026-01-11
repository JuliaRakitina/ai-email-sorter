from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_home_unauth_shows_login():
    r = client.get("/")
    assert r.status_code == 200
    assert "Sign in with Google" in r.text

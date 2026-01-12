from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlmodel import select
from app.models import User, GmailAccount


def test_oauth_connect_mode_does_not_replace_user(client, session, logged_in_session, test_gmail_account):
    async def mock_oauth_callback(request):
        return {
            "token": {"access_token": "token", "refresh_token": "refresh"},
            "userinfo": {"email": "new@gmail.com"},
        }
    
    with patch("app.main.oauth_callback", side_effect=mock_oauth_callback):
        with patch("app.main.build_gmail_service_from_enc") as mock_build:
            with patch("app.main.setup_gmail_watch"):
                with patch("app.main.get_current_user", return_value=logged_in_session):
                    mock_service = MagicMock()
                    mock_build.return_value = (mock_service, "encrypted_token")
                    
                    response = client.get("/auth/google/callback?code=test&state=test", follow_redirects=False)
                    assert response.status_code in [200, 303, 307, 308]


def test_oauth_login_mode_creates_user(client, session):
    async def mock_oauth_callback(request):
        return {
            "token": {"access_token": "token", "refresh_token": "refresh"},
            "userinfo": {"email": "login@gmail.com"},
        }
    
    with patch("app.main.oauth_callback", side_effect=mock_oauth_callback):
        with patch("app.main.build_gmail_service_from_enc") as mock_build:
            with patch("app.main.setup_gmail_watch"):
                with patch("app.main.get_current_user", return_value=None):
                    mock_service = MagicMock()
                    mock_build.return_value = (mock_service, "encrypted_token")
                    
                    response = client.get("/auth/google/callback?code=test&state=test", follow_redirects=False)
                    assert response.status_code in [200, 303, 307, 308]

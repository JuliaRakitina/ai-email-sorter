from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from sqlmodel import select
from app.models import Category, EmailRecord


def test_home_route_not_authenticated(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Sign in" in response.text or "Login" in response.text


def test_home_route_authenticated(client, session, logged_in_session, test_gmail_account, test_category):
    with patch("app.main.get_current_user") as mock_user:
        with patch("app.main.get_active_gmail_account") as mock_gmail:
            with patch("app.main.get_or_create_uncategorized", return_value=test_category):
                mock_user.return_value = logged_in_session
                mock_gmail.return_value = test_gmail_account
                
                response = client.get("/")
                assert response.status_code == 200


def test_category_create(client, session, logged_in_session, test_gmail_account):
    with patch("app.main.get_current_user") as mock_user:
        with patch("app.main.get_active_gmail_account") as mock_gmail:
            mock_user.return_value = logged_in_session
            mock_gmail.return_value = test_gmail_account
            
            response = client.post(
                "/categories/new",
                data={"name": "New Category", "description": "Description"},
            )
            assert response.status_code in [200, 303, 307, 308]


def test_category_detail(client, session, logged_in_session, test_gmail_account, test_category, test_email_record):
    with patch("app.main.get_current_user") as mock_user:
        with patch("app.main.get_active_gmail_account") as mock_gmail:
            mock_user.return_value = logged_in_session
            mock_gmail.return_value = test_gmail_account
            
            response = client.get(f"/categories/{test_category.id}")
            assert response.status_code == 200


def test_email_detail(client, session, logged_in_session, test_email_record):
    with patch("app.main.get_current_user") as mock_user:
        mock_user.return_value = logged_in_session
        
        response = client.get(f"/emails/{test_email_record.id}")
        assert response.status_code == 200


def test_select_account(client, session, logged_in_session, test_gmail_account):
    with patch("app.main.get_current_user") as mock_user:
        mock_user.return_value = logged_in_session
        
        response = client.post(f"/accounts/{test_gmail_account.id}/select")
        assert response.status_code in [200, 303, 307, 308]


def test_sync_route(client, session, logged_in_session, test_gmail_account, test_category):
    with patch("app.main.get_current_user") as mock_user:
        with patch("app.main.get_active_gmail_account") as mock_gmail:
            with patch("app.main.build_gmail_service_from_enc") as mock_build:
                with patch("app.main.list_message_ids", return_value=["msg1"]):
                    with patch("app.main.process_email_messages", return_value=1):
                        with patch("app.main.get_or_create_uncategorized", return_value=test_category):
                            mock_user.return_value = logged_in_session
                            mock_gmail.return_value = test_gmail_account
                            mock_service = MagicMock()
                            mock_build.return_value = (mock_service, "encrypted_token")
                            
                            response = client.post("/sync")
                            assert response.status_code in [200, 303, 307, 308]

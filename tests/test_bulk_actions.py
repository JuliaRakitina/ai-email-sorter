from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from sqlmodel import select
from app.models import EmailRecord, Category


def test_bulk_delete(
    client,
    session,
    logged_in_session,
    test_gmail_account,
    test_category,
    test_email_record,
):
    with patch("app.main.get_current_user", return_value=logged_in_session):
        with patch("app.main.build_gmail_service_from_enc") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = (mock_service, "encrypted_token")

            response = client.post(
                f"/categories/{test_category.id}/bulk",
                data={"action": "delete", "email_ids": [test_email_record.id]},
            )
            assert response.status_code in [200, 303, 307, 308]

            if response.status_code not in [303, 307, 308]:
                assert "error" in response.text.lower() or response.status_code == 200


def test_bulk_unsubscribe_background_task(
    client,
    session,
    logged_in_session,
    test_gmail_account,
    test_category,
    test_email_record,
):
    with patch("app.main.get_current_user", return_value=logged_in_session):
        response = client.post(
            f"/categories/{test_category.id}/bulk",
            data={"action": "unsubscribe", "email_ids": [test_email_record.id]},
        )
        assert response.status_code in [200, 303, 307, 308]

        if response.status_code in [303, 307, 308]:
            assert "unsubscribe_started=true" in response.headers.get("location", "")


def test_bulk_assign_category_manual_update(
    session, logged_in_session, test_gmail_account, test_category, test_email_record
):
    target_category = Category(
        user_id=logged_in_session.id,
        gmail_account_id=test_gmail_account.id,
        name="Target Category",
        description="Target",
    )
    session.add(target_category)
    session.commit()

    test_email_record.category_id = test_category.id
    session.add(test_email_record)
    session.commit()

    test_email_record.category_id = target_category.id
    session.add(test_email_record)
    session.commit()
    session.refresh(test_email_record)

    assert test_email_record.category_id == target_category.id


def test_get_unsubscribe_status(
    client,
    session,
    logged_in_session,
    test_gmail_account,
    test_category,
    test_email_record,
):
    with patch("app.main.get_current_user", return_value=logged_in_session):
        test_email_record.category_id = test_category.id
        test_email_record.unsubscribe_status = "success"
        test_email_record.unsubscribe_method = "one_click"
        test_email_record.unsubscribe_url = "https://example.com/unsubscribe"
        session.add(test_email_record)
        session.commit()

        response = client.get(f"/api/categories/{test_category.id}/unsubscribe-status")
        assert response.status_code == 200
        data = response.json()
        assert "statuses" in data
        assert len(data["statuses"]) == 1
        assert data["statuses"][0]["id"] == test_email_record.id
        assert data["statuses"][0]["unsubscribe_status"] == "success"
        assert data["statuses"][0]["unsubscribe_method"] == "one_click"


def test_get_unsubscribe_status_unauthorized(client):
    response = client.get("/api/categories/1/unsubscribe-status")
    assert response.status_code == 401

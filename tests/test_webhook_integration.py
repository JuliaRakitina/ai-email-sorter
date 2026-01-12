from __future__ import annotations
import pytest
import base64
import json
from unittest.mock import patch, MagicMock
from app.models import GmailAccount


def test_pubsub_webhook_valid(client, session, logged_in_session, test_gmail_account):
    message_data = {
        "emailAddress": test_gmail_account.email,
        "historyId": "12345",
    }
    data_json = json.dumps(message_data)
    data_b64 = base64.b64encode(data_json.encode()).decode()
    
    body = {"message": {"data": data_b64}}
    
    with patch("app.main.verify_pubsub_jwt", return_value=True):
        with patch("app.main.build_gmail_service_from_enc") as mock_build:
            with patch("app.main.sync_history", return_value="12345"):
                with patch("app.main.get_or_create_uncategorized"):
                    mock_service = MagicMock()
                    mock_build.return_value = (mock_service, "encrypted_token")
                    
                    response = client.post("/webhooks/pubsub", json=body)
                    assert response.status_code == 200


def test_pubsub_webhook_unknown_email(client, session):
    message_data = {
        "emailAddress": "unknown@example.com",
        "historyId": "12345",
    }
    data_json = json.dumps(message_data)
    data_b64 = base64.b64encode(data_json.encode()).decode()
    
    body = {"message": {"data": data_b64}}
    
    with patch("app.main.verify_pubsub_jwt", return_value=True):
        response = client.post("/webhooks/pubsub", json=body)
        assert response.status_code == 200

from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from app.gmail_watch import setup_gmail_watch


def test_setup_gmail_watch_success(session, test_gmail_account):
    mock_service = MagicMock()
    mock_response = {
        "historyId": "12345",
        "expiration": "1704110400000",
    }
    mock_service.users.return_value.watch.return_value.execute.return_value = mock_response
    
    with patch("app.gmail_watch.settings") as mock_settings:
        mock_settings.PUBSUB_TOPIC_NAME = "projects/test-project/topics/test-topic"
        mock_settings.GCP_PROJECT_ID = "test-project"
        
        result = setup_gmail_watch(mock_service, test_gmail_account, session)
        
        assert result is True
        assert test_gmail_account.watch_active is True
        assert test_gmail_account.last_history_id == "12345"


def test_setup_gmail_watch_no_topic_name(session, test_gmail_account):
    mock_service = MagicMock()
    
    with patch("app.gmail_watch.settings") as mock_settings:
        mock_settings.PUBSUB_TOPIC_NAME = ""
        mock_settings.GCP_PROJECT_ID = ""
        
        result = setup_gmail_watch(mock_service, test_gmail_account, session)
        
        assert result is False


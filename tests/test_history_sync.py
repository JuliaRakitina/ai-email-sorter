from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock, Mock
from app.history_sync import sync_history, fallback_query_sync


def test_sync_history_success(session, test_user, test_gmail_account, test_category):
    mock_service = MagicMock()
    mock_response = {
        "history": [
            {
                "historyId": "12346",
                "messagesAdded": [
                    {"message": {"id": "msg1"}},
                ],
            }
        ]
    }
    mock_service.users.return_value.history.return_value.list.return_value.execute.return_value = mock_response
    
    with patch("app.history_sync.process_email_messages", return_value=1):
        def get_uncat_func(sess, user, gmail_account):
            return test_category
        
        result = sync_history(
            mock_service,
            test_gmail_account,
            "12345",
            [test_category],
            session,
            test_user,
            get_uncat_func,
        )
        
        history_id, processed_count = result
        assert history_id == "12346"
        assert processed_count == 1
        assert test_gmail_account.last_history_id == "12346"


def test_sync_history_invalid_history_id(session, test_user, test_gmail_account, test_category):
    from googleapiclient.errors import HttpError
    
    mock_service = MagicMock()
    error_response = Mock()
    error_response.status = 400
    error_response.content = b"startHistoryId is invalid"
    mock_service.users.return_value.history.return_value.list.return_value.execute.side_effect = HttpError(
        error_response, b"startHistoryId is invalid"
    )
    
    with patch("app.history_sync.fallback_query_sync", return_value=("99999", 1)) as mock_fallback:
        with patch("app.gmail_watch.setup_gmail_watch"):
            def get_uncat_func(sess, user, gmail_account):
                return test_category
            
            result = sync_history(
                mock_service,
                test_gmail_account,
                "invalid",
                [test_category],
                session,
                test_user,
                get_uncat_func,
            )
            
            history_id, processed_count = result
            assert history_id == "99999"
            assert processed_count == 1
            mock_fallback.assert_called_once()


def test_fallback_query_sync(session, test_user, test_gmail_account, test_category):
    mock_service = MagicMock()
    mock_service.users.return_value.getProfile.return_value.execute.return_value = {
        "historyId": "99999"
    }
    
    with patch("app.history_sync.list_message_ids", return_value=["msg1"]):
        with patch("app.history_sync.process_email_messages", return_value=1):
            def get_uncat_func(sess, user, gmail_account):
                return test_category
            
            result = fallback_query_sync(
                mock_service,
                test_gmail_account,
                [test_category],
                session,
                test_user,
                get_uncat_func,
            )
            
            history_id, processed_count = result
            assert history_id == "99999"
            assert processed_count == 1

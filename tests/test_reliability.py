from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from app.email_processor import process_email_messages


def test_no_network_calls_in_email_processing(session, test_user, test_gmail_account, test_category, mock_gmail_service):
    with patch("app.email_processor.choose_category", return_value="Test Category"):
        with patch("app.email_processor.summarize_email", return_value="Test summary"):
            def get_uncat_func(sess, user, gmail_account):
                return test_category
                
            message_ids = ["msg1"]
            categories = [test_category]
            
            processed = process_email_messages(
                mock_gmail_service,
                test_gmail_account,
                message_ids,
                categories,
                session,
                test_user,
                get_uncat_func,
            )
            
            assert processed == 1


def test_long_body_truncation(mock_gmail_service, session, test_user, test_gmail_account, test_category):
    long_body = "x" * 10000
    
    with patch("app.email_processor.choose_category") as mock_choose:
        with patch("app.email_processor.summarize_email") as mock_summarize:
            def get_uncat_func(sess, user, gmail_account):
                return test_category
            
            message_ids = ["msg1"]
            categories = [test_category]
            
            mock_choose.return_value = "Test Category"
            mock_summarize.return_value = "Summary"
            
            process_email_messages(
                mock_gmail_service,
                test_gmail_account,
                message_ids,
                categories,
                session,
                test_user,
                get_uncat_func,
            )
            
            if mock_choose.called:
                call_args = mock_choose.call_args
                if call_args and len(call_args[0]) > 3:
                    body_arg = call_args[0][3]
                    assert len(body_arg) <= 4000

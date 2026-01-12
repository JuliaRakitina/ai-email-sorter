from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from sqlmodel import select
from app.email_processor import process_email_messages
from app.models import EmailRecord


def test_process_email_messages_new_emails(session, test_user, test_gmail_account, test_category, mock_gmail_service, mock_ai):
    def get_uncat_func(sess, user, gmail_account):
        return test_category
        
    message_ids = ["msg1", "msg2"]
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
    
    assert processed == 2
    emails = session.exec(select(EmailRecord)).all()
    assert len(emails) == 2
    assert all(e.gmail_account_id == test_gmail_account.id for e in emails)
    assert all(e.category_id == test_category.id for e in emails)
    assert all(e.archived_at is not None for e in emails)


def test_process_email_messages_idempotency(session, test_user, test_gmail_account, test_category, mock_gmail_service, mock_ai):
    existing = EmailRecord(
        gmail_account_id=test_gmail_account.id,
        category_id=test_category.id,
        gmail_message_id="msg1",
        from_email="test@example.com",
        subject="Test",
    )
    session.add(existing)
    session.commit()
    
    def get_uncat_func(sess, user, gmail_account):
        return test_category
        
    message_ids = ["msg1", "msg2"]
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
    emails = session.exec(select(EmailRecord)).all()
    assert len(emails) == 2


def test_process_email_messages_uncategorized(session, test_user, test_gmail_account, uncategorized_category, mock_gmail_service):
    with patch("app.email_processor.choose_category", return_value=None):
        with patch("app.email_processor.summarize_email", return_value="Summary"):
            def get_uncat_func(sess, user, gmail_account):
                return uncategorized_category
                
            message_ids = ["msg1"]
            categories = []
            
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
            emails = session.exec(select(EmailRecord)).all()
            assert len(emails) == 1
            assert emails[0].category_id == uncategorized_category.id


def test_process_email_messages_archives(mock_gmail_service, session, test_user, test_gmail_account, test_category, mock_ai):
    def get_uncat_func(sess, user, gmail_account):
        return test_category
        
    message_ids = ["msg1"]
    categories = [test_category]
    
    process_email_messages(
        mock_gmail_service,
        test_gmail_account,
        message_ids,
        categories,
        session,
        test_user,
        get_uncat_func,
    )
    
    mock_gmail_service.users.return_value.messages.return_value.modify.assert_called_once()


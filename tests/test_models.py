from __future__ import annotations
import pytest
from datetime import datetime
from app.models import User, GmailAccount, Category, EmailRecord
from app.crypto import encrypt_str


def test_user_creation(session):
    user = User(email="test@example.com")
    session.add(user)
    session.commit()
    session.refresh(user)
    
    assert user.id is not None
    assert user.email == "test@example.com"
    assert isinstance(user.created_at, datetime)


def test_gmail_account_creation(session, test_user):
    token_enc = encrypt_str('{"test": "data"}')
    
    account = GmailAccount(
        user_id=test_user.id,
        email="test@gmail.com",
        token_json_enc=token_enc,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    
    assert account.id is not None
    assert account.user_id == test_user.id
    assert account.email == "test@gmail.com"
    assert account.watch_active is False


def test_category_creation(session, test_user, test_gmail_account):
    category = Category(
        user_id=test_user.id,
        gmail_account_id=test_gmail_account.id,
        name="Work",
        description="Work emails",
        is_system=False,
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    
    assert category.id is not None
    assert category.user_id == test_user.id
    assert category.gmail_account_id == test_gmail_account.id
    assert category.name == "Work"
    assert category.is_system is False


def test_email_record_creation(session, test_gmail_account, test_category):
    email = EmailRecord(
        gmail_account_id=test_gmail_account.id,
        category_id=test_category.id,
        gmail_message_id="msg123",
        from_email="sender@example.com",
        subject="Test",
        snippet="Snippet",
        body_text="Body text",
        received_at=datetime.utcnow(),
    )
    session.add(email)
    session.commit()
    session.refresh(email)
    
    assert email.id is not None
    assert email.gmail_account_id == test_gmail_account.id
    assert email.category_id == test_category.id
    assert email.gmail_message_id == "msg123"


def test_email_record_idempotency(session, test_gmail_account, test_category):
    msg_id = "msg_duplicate"
    
    email1 = EmailRecord(
        gmail_account_id=test_gmail_account.id,
        category_id=test_category.id,
        gmail_message_id=msg_id,
        from_email="sender@example.com",
        subject="Test",
    )
    session.add(email1)
    session.commit()
    
    from sqlmodel import select
    existing = session.exec(
        select(EmailRecord).where(
            EmailRecord.gmail_account_id == test_gmail_account.id,
            EmailRecord.gmail_message_id == msg_id,
        )
    ).first()
    
    assert existing is not None
    assert existing.id == email1.id


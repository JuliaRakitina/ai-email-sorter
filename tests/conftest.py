from __future__ import annotations
import pytest
import os
import tempfile
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import Mock, MagicMock, patch

from sqlmodel import Session, create_engine, SQLModel
from fastapi.testclient import TestClient
from fastapi import Request

from app.db import get_session
from app.main import app
from app.models import User, GmailAccount, Category, EmailRecord
from app.crypto import encrypt_str


@pytest.fixture(scope="session")
def test_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass


@pytest.fixture(scope="function")
def test_engine(test_db_path):
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def session(test_engine):
    with Session(test_engine) as session:
        yield session
        session.rollback()


@pytest.fixture(scope="function")
def client(session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(session):
    user = User(email="test@example.com")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def logged_in_session(client, test_user):
    client.cookies.set("jump_session", "test_session")
    return test_user


@pytest.fixture
def test_gmail_account(session, test_user):
    token_data = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    encrypted_token = encrypt_str('{"access_token":"test","refresh_token":"test","token_type":"Bearer","expires_in":3600}')
    
    account = GmailAccount(
        user_id=test_user.id,
        email="test@gmail.com",
        token_json_enc=encrypted_token,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@pytest.fixture
def test_category(session, test_user, test_gmail_account):
    category = Category(
        user_id=test_user.id,
        gmail_account_id=test_gmail_account.id,
        name="Test Category",
        description="Test description",
        is_system=False,
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@pytest.fixture
def uncategorized_category(session, test_user, test_gmail_account):
    category = Category(
        user_id=test_user.id,
        gmail_account_id=test_gmail_account.id,
        name="Uncategorized",
        description="Emails not categorized yet",
        is_system=True,
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@pytest.fixture
def test_email_record(session, test_gmail_account, test_category):
    email = EmailRecord(
        gmail_account_id=test_gmail_account.id,
        category_id=test_category.id,
        gmail_message_id="test_message_id",
        from_email="sender@example.com",
        subject="Test Subject",
        snippet="Test snippet",
        body_text="Test body",
        received_at=datetime.utcnow(),
    )
    session.add(email)
    session.commit()
    session.refresh(email)
    return email


@pytest.fixture
def mock_gmail_service():
    service = MagicMock()
    
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg1"}, {"id": "msg2"}]
    }
    
    service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "id": "msg1",
        "threadId": "thread1",
        "snippet": "Test snippet",
        "payload": {
            "headers": [
                {"name": "From", "value": "test@example.com"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Mon, 1 Jan 2024 12:00:00 +0000"},
            ],
            "body": {"data": "dGVzdCBib2R5"},
            "parts": [],
        },
        "internalDate": "1704110400000",
    }
    
    service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}
    service.users.return_value.messages.return_value.trash.return_value.execute.return_value = {}
    service.users.return_value.history.return_value.list.return_value.execute.return_value = {
        "history": []
    }
    service.users.return_value.watch.return_value.execute.return_value = {
        "historyId": "12345",
        "expiration": "1704110400000",
    }
    service.users.return_value.getProfile.return_value.execute.return_value = {
        "historyId": "12345"
    }
    
    return service


@pytest.fixture
def mock_ai():
    with patch("app.ai._client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        
        def choose_side_effect(categories, subject, snippet, body_text):
            if not categories:
                return None
            return categories[0].name if categories else None
        
        def summarize_side_effect(subject, from_email, body_text):
            return f"Summary: {subject}"
        
        with patch("app.email_processor.choose_category", side_effect=choose_side_effect):
            with patch("app.email_processor.summarize_email", side_effect=summarize_side_effect):
                yield mock_client

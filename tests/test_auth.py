from __future__ import annotations
import pytest
from unittest.mock import Mock, patch
from fastapi import Request
from sqlmodel import select
from app.main import get_current_user, get_active_gmail_account
from app.models import User, GmailAccount


def test_get_current_user(session, test_user):
    request = Mock(spec=Request)
    request.session = {"user_email": test_user.email}
    
    user = get_current_user(request, session)
    assert user is not None
    assert user.id == test_user.id
    assert user.email == test_user.email


def test_get_current_user_no_session(session):
    request = Mock(spec=Request)
    request.session = {}
    
    user = get_current_user(request, session)
    assert user is None


def test_get_active_gmail_account(session, test_user, test_gmail_account):
    request = Mock(spec=Request)
    request.session = {"active_gmail_account_id": test_gmail_account.id}
    
    active = get_active_gmail_account(request, session, test_user)
    assert active is not None
    assert active.id == test_gmail_account.id


def test_get_active_gmail_account_defaults_to_first(session, test_user, test_gmail_account):
    request = Mock(spec=Request)
    request.session = {}
    
    active = get_active_gmail_account(request, session, test_user)
    assert active is not None
    assert active.id == test_gmail_account.id
    assert "active_gmail_account_id" in request.session


def test_get_active_gmail_account_invalid_id(session, test_user, test_gmail_account):
    request = Mock(spec=Request)
    request.session = {"active_gmail_account_id": 99999}
    
    active = get_active_gmail_account(request, session, test_user)
    assert active is not None
    assert active.id == test_gmail_account.id


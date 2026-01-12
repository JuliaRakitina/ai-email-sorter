from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
from sqlmodel import Session
from app.models import EmailRecord
from app.unsubscribe_agent import UnsubscribeTarget
from app.main import process_unsubscribe_background


def test_process_unsubscribe_background_success(test_engine, test_gmail_account, test_category, test_email_record):
    email_id = test_email_record.id
    category_id = test_category.id
    
    with Session(test_engine) as session:
        rec = session.get(EmailRecord, email_id)
        rec.category_id = category_id
        session.add(rec)
        session.commit()
    
    with patch("app.db.engine", test_engine):
        with patch("app.main.build_gmail_service_from_enc") as mock_build:
            with patch("app.main.extract_headers") as mock_extract_headers:
                with patch("app.main.extract_bodies") as mock_extract_bodies:
                    with patch("app.main.discover_unsubscribe_target") as mock_discover:
                        with patch("app.main.attempt_unsubscribe") as mock_attempt:
                            with patch("httpx.Client") as mock_client_class:
                                mock_service = MagicMock()
                                mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
                                    "id": "msg1",
                                    "payload": {"headers": []},
                                }
                                mock_build.return_value = (mock_service, "encrypted_token")
                                mock_extract_headers.return_value = {
                                    "list-unsubscribe": "<https://example.com/unsubscribe>",
                                }
                                mock_extract_bodies.return_value = ("", "")
                                
                                target = UnsubscribeTarget(
                                    url="https://example.com/unsubscribe",
                                    has_one_click=True,
                                    source="header_link"
                                )
                                mock_discover.return_value = target
                                mock_attempt.return_value = ("success", "one_click", None)
                                
                                mock_client = MagicMock()
                                mock_client_class.return_value.__enter__.return_value = mock_client
                                
                                process_unsubscribe_background(email_id, category_id)
    
    with Session(test_engine) as session:
        rec = session.get(EmailRecord, email_id)
        assert rec.unsubscribe_status == "success"
        assert rec.unsubscribe_method == "one_click"
        assert rec.unsubscribed_at is not None
        assert rec.unsubscribe_url == "https://example.com/unsubscribe"


def test_process_unsubscribe_background_no_target(test_engine, test_gmail_account, test_category, test_email_record):
    email_id = test_email_record.id
    category_id = test_category.id
    
    with Session(test_engine) as session:
        rec = session.get(EmailRecord, email_id)
        rec.category_id = category_id
        session.add(rec)
        session.commit()
    
    with patch("app.db.engine", test_engine):
        with patch("app.main.build_gmail_service_from_enc") as mock_build:
            with patch("app.main.extract_headers") as mock_extract_headers:
                with patch("app.main.extract_bodies") as mock_extract_bodies:
                    with patch("app.main.discover_unsubscribe_target") as mock_discover:
                        mock_service = MagicMock()
                        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
                            "id": "msg1",
                            "payload": {"headers": []},
                        }
                        mock_build.return_value = (mock_service, "encrypted_token")
                        mock_extract_headers.return_value = {}
                        mock_extract_bodies.return_value = ("", "")
                        mock_discover.return_value = None
                        
                        process_unsubscribe_background(email_id, category_id)
    
    with Session(test_engine) as session:
        rec = session.get(EmailRecord, email_id)
        assert rec.unsubscribe_status == "failed"
        assert rec.unsubscribe_error == "No unsubscribe URL found"


def test_process_unsubscribe_background_failed(test_engine, test_gmail_account, test_category, test_email_record):
    email_id = test_email_record.id
    category_id = test_category.id
    
    with Session(test_engine) as session:
        rec = session.get(EmailRecord, email_id)
        rec.category_id = category_id
        session.add(rec)
        session.commit()
    
    with patch("app.db.engine", test_engine):
        with patch("app.main.build_gmail_service_from_enc") as mock_build:
            with patch("app.main.extract_headers") as mock_extract_headers:
                with patch("app.main.extract_bodies") as mock_extract_bodies:
                    with patch("app.main.discover_unsubscribe_target") as mock_discover:
                        with patch("app.main.attempt_unsubscribe") as mock_attempt:
                            with patch("httpx.Client") as mock_client_class:
                                mock_service = MagicMock()
                                mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
                                    "id": "msg1",
                                    "payload": {"headers": []},
                                }
                                mock_build.return_value = (mock_service, "encrypted_token")
                                mock_extract_headers.return_value = {
                                    "list-unsubscribe": "<https://example.com/unsubscribe>",
                                }
                                mock_extract_bodies.return_value = ("", "")
                                
                                target = UnsubscribeTarget(
                                    url="https://example.com/unsubscribe",
                                    has_one_click=False,
                                    source="header_link"
                                )
                                mock_discover.return_value = target
                                mock_attempt.return_value = ("failed", "header_link", "Network error")
                                
                                mock_client = MagicMock()
                                mock_client_class.return_value.__enter__.return_value = mock_client
                                
                                process_unsubscribe_background(email_id, category_id)
    
    with Session(test_engine) as session:
        rec = session.get(EmailRecord, email_id)
        assert rec.unsubscribe_status == "failed"
        assert rec.unsubscribe_method == "header_link"
        assert rec.unsubscribe_error == "Network error"
        assert rec.unsubscribed_at is None


from __future__ import annotations
import pytest
import base64
from datetime import datetime
from unittest.mock import MagicMock
from app.gmail_service import (
    extract_headers,
    extract_bodies,
    parse_internal_date_ms,
    list_message_ids,
    archive_message,
    trash_message,
)


def test_extract_headers():
    message = {
        "payload": {
            "headers": [
                {"name": "From", "value": "test@example.com"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "Mon, 1 Jan 2024 12:00:00 +0000"},
            ]
        }
    }
    headers = extract_headers(message)
    
    assert headers["from"] == "test@example.com"
    assert headers["subject"] == "Test Subject"
    assert headers["date"] == "Mon, 1 Jan 2024 12:00:00 +0000"


def test_extract_bodies_text_only():
    body_text = "test body"
    body_bytes = body_text.encode('utf-8')
    body_b64 = base64.urlsafe_b64encode(body_bytes).decode('ascii')
    
    message = {
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": body_b64},
            "parts": [],
        }
    }
    extracted_text, extracted_html = extract_bodies(message)
    
    assert extracted_text == body_text
    assert extracted_html is None


def test_extract_bodies_html():
    html_content = "<p>Test</p>"
    html_bytes = html_content.encode('utf-8')
    html_b64 = base64.urlsafe_b64encode(html_bytes).decode('ascii').rstrip('=')
    
    text_content = "test"
    text_bytes = text_content.encode('utf-8')
    text_b64 = base64.urlsafe_b64encode(text_bytes).decode('ascii').rstrip('=')
    
    message = {
        "payload": {
            "body": {"data": ""},
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": text_b64},
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": html_b64},
                },
            ],
        }
    }
    body_text, body_html = extract_bodies(message)
    
    assert body_text == text_content
    assert body_html == html_content


def test_parse_internal_date_ms():
    message = {"internalDate": "1704110400000"}
    dt = parse_internal_date_ms(message)
    
    assert isinstance(dt, datetime)
    assert dt.year == 2024


def test_list_message_ids(mock_gmail_service):
    ids = list_message_ids(mock_gmail_service, "me", "in:inbox", max_results=10)
    
    assert len(ids) == 2
    assert ids[0] == "msg1"
    assert ids[1] == "msg2"


def test_archive_message(mock_gmail_service):
    archive_message(mock_gmail_service, "me", "msg1")
    
    mock_gmail_service.users.return_value.messages.return_value.modify.assert_called_once()


def test_trash_message(mock_gmail_service):
    trash_message(mock_gmail_service, "me", "msg1")
    
    mock_gmail_service.users.return_value.messages.return_value.trash.assert_called_once()

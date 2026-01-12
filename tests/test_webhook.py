from __future__ import annotations
import pytest
import base64
import json
from unittest.mock import Mock, patch
from fastapi import Request
from app.pubsub_webhook import verify_pubsub_jwt, parse_pubsub_message


def test_parse_pubsub_message():
    message_data = {"emailAddress": "test@example.com", "historyId": "12345"}
    data_json = json.dumps(message_data)
    data_b64 = base64.b64encode(data_json.encode()).decode()
    
    body = {
        "message": {
            "data": data_b64,
        }
    }
    
    result = parse_pubsub_message(body)
    
    assert result is not None
    assert result["emailAddress"] == "test@example.com"
    assert result["historyId"] == "12345"


def test_parse_pubsub_message_no_message():
    body = {}
    result = parse_pubsub_message(body)
    assert result is None


def test_parse_pubsub_message_no_data():
    body = {"message": {}}
    result = parse_pubsub_message(body)
    assert result is None


def test_verify_pubsub_jwt_no_header():
    request = Mock(spec=Request)
    request.headers = {}
    
    with patch("app.pubsub_webhook.settings") as mock_settings:
        mock_settings.PUBSUB_PUSH_AUDIENCE = "test-audience"
        result = verify_pubsub_jwt(request)
        assert result is False


def test_verify_pubsub_jwt_valid():
    request = Mock(spec=Request)
    request.headers = {"Authorization": "Bearer valid_token"}
    
    with patch("app.pubsub_webhook.settings") as mock_settings:
        mock_settings.PUBSUB_PUSH_AUDIENCE = "test-audience"
        with patch("app.pubsub_webhook.id_token.verify_token", return_value={}):
            result = verify_pubsub_jwt(request)
            assert result is True


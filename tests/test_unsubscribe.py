from __future__ import annotations
import pytest
from unittest.mock import MagicMock, Mock, patch
from app.unsubscribe_agent import (
    parse_list_unsubscribe,
    attempt_one_click_unsubscribe,
    attempt_form_unsubscribe,
    best_effort_unsubscribe,
)


def test_parse_list_unsubscribe_one_click():
    headers = {
        "list-unsubscribe": "<https://example.com/unsubscribe>",
        "list-unsubscribe-post": "List-Unsubscribe=One-Click",
    }
    url, has_one_click = parse_list_unsubscribe(headers)
    
    assert url == "https://example.com/unsubscribe"
    assert has_one_click is True


def test_parse_list_unsubscribe_no_one_click():
    headers = {
        "list-unsubscribe": "<https://example.com/unsubscribe>",
    }
    url, has_one_click = parse_list_unsubscribe(headers)
    
    assert url == "https://example.com/unsubscribe"
    assert has_one_click is False


def test_parse_list_unsubscribe_no_header():
    headers = {}
    url, has_one_click = parse_list_unsubscribe(headers)
    
    assert url is None
    assert has_one_click is False


def test_attempt_one_click_unsubscribe_success():
    http_client = MagicMock()
    response = Mock()
    response.status_code = 200
    http_client.post.return_value = response
    
    success, msg = attempt_one_click_unsubscribe(http_client, "https://example.com/unsubscribe")
    
    assert success is True
    assert "successful" in msg.lower()
    http_client.post.assert_called_once()


def test_attempt_one_click_unsubscribe_failure():
    http_client = MagicMock()
    response = Mock()
    response.status_code = 400
    http_client.post.return_value = response
    
    success, msg = attempt_one_click_unsubscribe(http_client, "https://example.com/unsubscribe")
    
    assert success is False


def test_attempt_form_unsubscribe_success():
    http_client = MagicMock()
    
    get_response = Mock()
    get_response.status_code = 200
    get_response.text = '<form action="/unsubscribe"><input name="email"/><button>Unsubscribe</button></form>'
    http_client.get.return_value = get_response
    
    post_response = Mock()
    post_response.status_code = 200
    post_response.text = '<title>Success</title><div>Unsubscribed</div>'
    http_client.post.return_value = post_response
    
    success, msg = attempt_form_unsubscribe(http_client, "https://example.com/unsubscribe")
    
    assert success is True


def test_best_effort_unsubscribe_one_click():
    http_client = MagicMock()
    headers = {
        "list-unsubscribe": "<https://example.com/unsubscribe>",
        "list-unsubscribe-post": "List-Unsubscribe=One-Click",
    }
    
    response = Mock()
    response.status_code = 200
    http_client.post.return_value = response
    
    success, msg = best_effort_unsubscribe(http_client, headers, "")
    
    assert success is True
    http_client.post.assert_called_once()


def test_best_effort_unsubscribe_no_url():
    http_client = MagicMock()
    headers = {}
    
    success, msg = best_effort_unsubscribe(http_client, headers, "")
    
    assert success is False
    assert "no unsubscribe url" in msg.lower()


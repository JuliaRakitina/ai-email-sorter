from __future__ import annotations
import pytest
from unittest.mock import MagicMock, Mock, patch
from app.unsubscribe_agent import (
    parse_list_unsubscribe,
    attempt_one_click_unsubscribe,
    attempt_form_unsubscribe,
    best_effort_unsubscribe,
    discover_unsubscribe_target,
    attempt_unsubscribe,
    UnsubscribeTarget,
    find_unsubscribe_links_in_html,
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


def test_discover_unsubscribe_target_from_header():
    headers = {
        "list-unsubscribe": "<https://example.com/unsubscribe>",
        "list-unsubscribe-post": "List-Unsubscribe=One-Click",
    }
    target = discover_unsubscribe_target(headers, "")
    
    assert target is not None
    assert target.url == "https://example.com/unsubscribe"
    assert target.has_one_click is True
    assert target.source == "header_link"


def test_discover_unsubscribe_target_from_html():
    headers = {}
    html = '<html><body><a href="https://example.com/unsubscribe">Unsubscribe</a></body></html>'
    target = discover_unsubscribe_target(headers, html)
    
    assert target is not None
    assert target.url == "https://example.com/unsubscribe"
    assert target.has_one_click is False
    assert target.source == "body_link"


def test_discover_unsubscribe_target_no_target():
    headers = {}
    html = '<html><body><p>No unsubscribe link</p></body></html>'
    target = discover_unsubscribe_target(headers, html)
    
    assert target is None


def test_find_unsubscribe_links_in_html():
    html = '<html><body><a href="https://example.com/unsubscribe">Unsubscribe</a><a href="https://other.com">Other</a></body></html>'
    links = find_unsubscribe_links_in_html(html)
    
    assert len(links) == 1
    assert links[0] == "https://example.com/unsubscribe"


def test_find_unsubscribe_links_in_html_empty():
    html = '<html><body><p>No links</p></body></html>'
    links = find_unsubscribe_links_in_html(html)
    
    assert len(links) == 0


def test_attempt_unsubscribe_one_click_success():
    http_client = MagicMock()
    response = Mock()
    response.status_code = 200
    http_client.post.return_value = response
    
    target = UnsubscribeTarget(
        url="https://example.com/unsubscribe",
        has_one_click=True,
        source="header_link"
    )
    
    status, method, error = attempt_unsubscribe(http_client, target)
    
    assert status == "success"
    assert method == "one_click"
    assert error is None
    http_client.post.assert_called_once()


def test_attempt_unsubscribe_one_click_failure():
    http_client = MagicMock()
    response = Mock()
    response.status_code = 400
    http_client.post.return_value = response
    
    target = UnsubscribeTarget(
        url="https://example.com/unsubscribe",
        has_one_click=True,
        source="header_link"
    )
    
    status, method, error = attempt_unsubscribe(http_client, target)
    
    assert status == "attempted"
    assert method == "one_click"
    assert error is not None


def test_attempt_unsubscribe_form_success():
    http_client = MagicMock()
    
    get_response = Mock()
    get_response.status_code = 200
    get_response.text = '<form action="/unsubscribe"><input name="email"/><button>Unsubscribe</button></form>'
    http_client.get.return_value = get_response
    
    post_response = Mock()
    post_response.status_code = 200
    post_response.text = '<title>Success</title><div>Unsubscribed</div>'
    http_client.post.return_value = post_response
    
    target = UnsubscribeTarget(
        url="https://example.com/unsubscribe",
        has_one_click=False,
        source="header_link"
    )
    
    status, method, error = attempt_unsubscribe(http_client, target)
    
    assert status == "success"
    assert method == "header_link"
    assert error is None


def test_attempt_unsubscribe_form_no_form():
    http_client = MagicMock()
    
    get_response = Mock()
    get_response.status_code = 200
    get_response.text = '<html><body><p>No form here</p></body></html>'
    http_client.get.return_value = get_response
    
    target = UnsubscribeTarget(
        url="https://example.com/unsubscribe",
        has_one_click=False,
        source="body_link"
    )
    
    status, method, error = attempt_unsubscribe(http_client, target)
    
    assert status == "manual_required"
    assert method == "body_link"
    assert "No unsubscribe form found" in error


def test_attempt_unsubscribe_exception():
    http_client = MagicMock()
    http_client.get.side_effect = Exception("Network error")
    
    target = UnsubscribeTarget(
        url="https://example.com/unsubscribe",
        has_one_click=False,
        source="header_link"
    )
    
    status, method, error = attempt_unsubscribe(http_client, target)
    
    assert status == "failed"
    assert method == "header_link"
    assert "Network error" in error


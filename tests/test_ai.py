from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from app.ai import choose_category, summarize_email
from app.models import Category


def test_choose_category():
    categories = [
        Category(id=1, name="Work", description="Work emails", user_id=1, gmail_account_id=1),
        Category(id=2, name="Personal", description="Personal emails", user_id=1, gmail_account_id=1),
    ]
    
    with patch("app.ai._client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"category_name": "Work"}'
        mock_client.chat.completions.create.return_value = mock_response
        
        result = choose_category(categories, "Meeting", "snippet", "body")
        
        assert result == "Work"


def test_choose_category_no_match():
    categories = [
        Category(id=1, name="Work", description="Work emails", user_id=1, gmail_account_id=1),
    ]
    
    with patch("app.ai._client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"category_name": "Invalid"}'
        mock_client.chat.completions.create.return_value = mock_response
        
        result = choose_category(categories, "Meeting", "snippet", "body")
        
        assert result is None


def test_choose_category_empty_list():
    result = choose_category([], "Meeting", "snippet", "body")
    assert result is None


def test_summarize_email():
    with patch("app.ai._client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary text"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = summarize_email("Subject", "from@example.com", "Body text")
        
        assert result == "Summary text"


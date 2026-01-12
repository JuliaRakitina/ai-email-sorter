# Test Suite

Comprehensive test suite for the Jump AI Email Sorter application.

## Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_routes.py

# Run with coverage
pytest --cov=app --cov-report=html
```

## Test Organization

- `test_auth.py` - Authentication and session management
- `test_models.py` - Database models and idempotency
- `test_gmail_service.py` - Gmail API service functions
- `test_email_processing.py` - Email processing pipeline
- `test_unsubscribe.py` - Unsubscribe agent functionality
- `test_history_sync.py` - History synchronization
- `test_webhook.py` - Pub/Sub webhook parsing
- `test_webhook_integration.py` - Pub/Sub webhook integration
- `test_routes.py` - FastAPI routes and endpoints
- `test_bulk_actions.py` - Bulk delete, unsubscribe, assign
- `test_oauth_modes.py` - OAuth login vs connect modes
- `test_gmail_watch.py` - Gmail watch setup
- `test_ai.py` - AI categorization and summarization
- `test_reliability.py` - Network call blocking, edge cases

## Features

- **Zero network calls**: All external APIs are mocked
- **Isolated database**: Each test uses a temporary SQLite database
- **Fast execution**: Tests complete in seconds
- **Deterministic**: Tests pass reliably on Python 3.11.9


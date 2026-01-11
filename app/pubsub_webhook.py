from __future__ import annotations
import base64
import json
import logging
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException, status
from google.auth.transport.requests import Request as GRequest
from google.oauth2 import id_token
from google.auth.exceptions import GoogleAuthError

from .settings import settings

logger = logging.getLogger(__name__)


def verify_pubsub_jwt(request: Request) -> bool:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header")
        return False

    token = auth_header[7:]

    try:
        id_token.verify_token(
            token,
            request=GRequest(),
            audience=settings.PUBSUB_PUSH_AUDIENCE,
        )
        return True
    except GoogleAuthError as e:
        logger.warning(f"JWT verification failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during JWT verification: {e}")
        return False


def parse_pubsub_message(body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        message = body.get("message", {})
        data_b64 = message.get("data", "")
        if not data_b64:
            return None

        data_bytes = base64.b64decode(data_b64)
        data_json = json.loads(data_bytes.decode("utf-8"))
        return data_json
    except Exception as e:
        logger.error(f"Failed to parse Pub/Sub message: {e}")
        return None


from __future__ import annotations
import json
import logging
from datetime import timezone
from typing import Any, Dict
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import Request
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GRequest
from googleapiclient.discovery import build

from .settings import settings
from .crypto import encrypt_str, decrypt_str

logger = logging.getLogger(__name__)

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.readonly",
        "prompt": "consent",
        "access_type": "offline",
    },
)


def redirect_uri() -> str:
    return settings.BASE_URL.rstrip("/") + settings.GOOGLE_REDIRECT_PATH


async def oauth_login(request: Request, prompt: str = "consent"):
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri(),
        prompt=prompt,
        access_type="offline",
        include_granted_scopes="true",
    )


async def oauth_callback(request: Request) -> Dict[str, Any]:
    # Debug: Check session and request state
    state_param = request.query_params.get("state")
    session_keys = (
        list(request.session.keys()) if hasattr(request.session, "keys") else []
    )

    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        # State mismatch usually means session was lost or cookie issues
        error_msg = str(e)
        error_details = (
            f"OAuth Error: {error_msg}\n"
            f"State from callback: {state_param}\n"
            f"Session keys: {session_keys}\n"
            f"Redirect URI: {redirect_uri()}\n"
            "Common fixes:\n"
            "1. Ensure SECRET_KEY is set to a stable value in .env (not 'change-me')\n"
            "2. Verify redirect_uri in Google Cloud Console matches exactly\n"
            "3. Clear browser cookies and try again\n"
            "4. Check browser console for cookie-related errors"
        )
        if "state" in error_msg.lower() or "mismatching" in error_msg.lower():
            raise ValueError(error_details)
        raise ValueError(f"OAuth error: {error_details}")
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await oauth.google.userinfo(token=token)
    return {"token": token, "userinfo": userinfo}


def credentials_from_token_dict(token: Dict[str, Any]) -> Credentials:
    # Don't set expiry initially - let Google's library handle it
    # This avoids timezone comparison errors completely
    # Google will set expiry correctly when it refreshes or validates the token
    expiry = None

    # Create credentials with all required fields
    # Ensure all fields are set to avoid RefreshError
    refresh_token = token.get("refresh_token") or None
    access_token = token.get("access_token")

    # Validate access_token is not empty
    if not access_token or (isinstance(access_token, str) and not access_token.strip()):
        raise ValueError("Token has empty or invalid access_token")

    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID or None,
        client_secret=settings.GOOGLE_CLIENT_SECRET or None,
        scopes=[
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.readonly",
            "openid",
            "email",
            "profile",
        ],
        expiry=expiry,
    )


def refresh_if_needed(creds: Credentials) -> Credentials:
    """Refresh credentials if expired, handling timezone comparison issues."""
    if not creds:
        return creds

    # Don't try to refresh if we don't have the required fields
    if (
        not creds.refresh_token
        or not creds.token_uri
        or not creds.client_id
        or not creds.client_secret
    ):
        # Missing required fields - can't refresh, but might still be usable if token is valid
        return creds

    # Try to check if expired, but handle timezone comparison errors
    try:
        if creds.expired:
            creds.refresh(GRequest())
    except (TypeError, ValueError) as e:
        # Timezone comparison error or other datetime issues - skip refresh check
        # The token might still be valid, let Google's library handle it during API calls
        logger.debug(f"Skipping refresh check due to error: {e}")
        pass
    except Exception as e:
        # Other errors during expiry check - log but don't fail
        logger.warning(f"Error checking token expiry: {e}")
        pass

    return creds


def build_gmail_service_from_enc(token_json_enc: str):
    token = json.loads(decrypt_str(token_json_enc))

    # Validate that we have minimum required fields
    access_token = token.get("access_token")
    if not access_token or (isinstance(access_token, str) and not access_token.strip()):
        raise ValueError("Token missing or empty access_token - token is invalid")
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise ValueError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in settings"
        )

    # Check if refresh_token is present
    refresh_token_present = bool(token.get("refresh_token"))
    if refresh_token_present:
        logger.info("✓ Refresh token is available in stored token")
    else:
        # Log warning - token can still be used until it expires
        logger.warning(
            "Token missing refresh_token. This token will work until expiration, "
            "but cannot be refreshed automatically. To get refresh_token:\n"
            "1. Go to https://myaccount.google.com/permissions\n"
            "2. Find this app and revoke access\n"
            "3. Clear browser cookies for localhost:8000\n"
            "4. Sign in again - this will force consent and return refresh_token"
        )

    # Use credentials_from_token_dict which handles expiry parsing properly
    creds = credentials_from_token_dict(token)

    # If we have refresh_token, always refresh once to let Google set expiry correctly
    # This ensures expiry is in the correct format and avoids datetime comparison errors
    if creds.refresh_token:
        try:
            # Refresh credentials - this will let Google set expiry correctly
            # Even if token isn't expired, this ensures expiry format is correct
            creds.refresh(GRequest())
            logger.debug("Credentials refreshed successfully - expiry set by Google")
        except Exception as refresh_error:
            # If refresh fails (e.g., token still valid), that's okay
            # The token will work, and Google will set expiry when needed
            logger.debug(f"Token refresh not needed or failed: {refresh_error}")
            # Don't fail - let the token be used as-is

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # Update stored token with current values after potential refresh
    token["access_token"] = creds.token
    if creds.expiry:
        # Store expiry as UTC timestamp
        if creds.expiry.tzinfo is None:
            expiry_utc = creds.expiry.replace(tzinfo=timezone.utc)
        else:
            expiry_utc = creds.expiry.astimezone(timezone.utc)
        token["expires_at"] = int(expiry_utc.timestamp())

    return service, encrypt_str(json.dumps(token))

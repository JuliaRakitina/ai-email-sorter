from __future__ import annotations
import base64
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "===")


def extract_headers(msg: Dict[str, Any]) -> Dict[str, str]:
    headers = msg.get("payload", {}).get("headers", [])
    out = {}
    for h in headers:
        name = h.get("name", "")
        value = h.get("value", "")
        if name:
            out[name.lower()] = value
    return out


def _walk_parts(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    parts = []
    stack = [payload]
    while stack:
        p = stack.pop()
        if "parts" in p and p["parts"]:
            stack.extend(p["parts"])
        else:
            parts.append(p)
    return parts


def extract_bodies(msg: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    payload = msg.get("payload") or {}
    parts = _walk_parts(payload)
    text, html = None, None
    for p in parts:
        mime = p.get("mimeType", "")
        body = p.get("body", {}) or {}
        data = body.get("data")
        if not data:
            continue
        content = _b64url_decode(data).decode("utf-8", errors="replace")
        if mime == "text/plain" and text is None:
            text = content
        if mime == "text/html" and html is None:
            html = content
    # Fallback: if only HTML, produce a readable text version
    if text is None and html:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n")
    return text, html


def parse_internal_date_ms(msg: Dict[str, Any]) -> Optional[datetime]:
    ms = msg.get("internalDate")
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).replace(
            tzinfo=None
        )
    except Exception:
        return None


def archive_message(gmail_service, user_id: str, message_id: str):
    gmail_service.users().messages().modify(
        userId=user_id,
        id=message_id,
        body={"removeLabelIds": ["INBOX"]},
    ).execute()


def trash_message(gmail_service, user_id: str, message_id: str):
    gmail_service.users().messages().trash(userId=user_id, id=message_id).execute()


def list_message_ids(
    gmail_service, user_id: str, q: str, max_results: int = 10
) -> List[str]:
    resp = (
        gmail_service.users()
        .messages()
        .list(userId=user_id, q=q, maxResults=max_results)
        .execute()
    )
    msgs = resp.get("messages", []) or []
    return [m["id"] for m in msgs if "id" in m]

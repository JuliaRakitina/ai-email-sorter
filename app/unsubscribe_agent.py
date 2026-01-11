from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup

@dataclass
class UnsubLink:
    kind: str  # 'mailto' or 'http'
    value: str

def parse_list_unsubscribe(headers: dict) -> List[UnsubLink]:
    # Gmail returns raw headers in payload.headers. We store lower-case keys.
    raw = headers.get("list-unsubscribe") or headers.get("list-unsubscribe-post") or ""
    if not raw:
        return []
    # Links appear like: <mailto:...>, <https://...>
    links = re.findall(r"<([^>]+)>", raw)
    out: List[UnsubLink] = []
    for l in links:
        l = l.strip()
        if l.startswith("mailto:"):
            out.append(UnsubLink(kind="mailto", value=l))
        elif l.startswith("http://") or l.startswith("https://"):
            out.append(UnsubLink(kind="http", value=l))
    return out

def find_unsubscribe_links_in_html(html: str) -> List[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    urls = []
    for a in soup.find_all("a"):
        text = (a.get_text(" ") or "").strip().lower()
        href = a.get("href") or ""
        if "unsubscribe" in text or "unsubscribe" in href.lower():
            if href.startswith("http://") or href.startswith("https://"):
                urls.append(href)
    # de-dup preserve order
    seen = set()
    dedup = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup[:5]

def best_effort_unsubscribe(http_client, headers: dict, html: str) -> Tuple[bool, str]:
    # Priority: List-Unsubscribe (http), then html links.
    links = parse_list_unsubscribe(headers)
    http_links = [l.value for l in links if l.kind == "http"]
    if http_links:
        try:
            r = http_client.get(http_links[0], follow_redirects=True, timeout=20)
            if r.status_code < 400:
                return True, f"Opened unsubscribe URL (status {r.status_code})."
            return False, f"Unsubscribe URL returned {r.status_code}."
        except Exception as e:
            return False, f"HTTP unsubscribe failed: {e}"
    html_links = find_unsubscribe_links_in_html(html or "")
    if html_links:
        try:
            r = http_client.get(html_links[0], follow_redirects=True, timeout=20)
            if r.status_code < 400:
                return True, f"Opened unsubscribe URL from email body (status {r.status_code})."
            return False, f"Unsubscribe body URL returned {r.status_code}."
        except Exception as e:
            return False, f"HTTP unsubscribe failed: {e}"
    # mailto requires sending an email; not done here for safety / complexity.
    mailto_links = [l.value for l in links if l.kind == "mailto"]
    if mailto_links:
        return False, "Found mailto unsubscribe, but auto-sending unsubscribe email is not implemented."
    return False, "No unsubscribe link found."

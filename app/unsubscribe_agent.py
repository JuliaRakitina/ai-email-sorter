from __future__ import annotations
import logging
import re
from typing import Optional, Tuple
from dataclasses import dataclass
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


@dataclass
class UnsubscribeTarget:
    url: str
    has_one_click: bool
    source: str


def parse_list_unsubscribe(headers: dict) -> Tuple[Optional[str], bool]:
    print("[Unsubscribe] Parsing List-Unsubscribe headers...")
    list_unsubscribe = headers.get("list-unsubscribe", "")
    list_unsubscribe_post = headers.get("list-unsubscribe-post", "")

    if not list_unsubscribe:
        print("[Unsubscribe] No List-Unsubscribe header found")
        logger.info("No List-Unsubscribe header found")
        return None, False

    print(f"[Unsubscribe] List-Unsubscribe header: {list_unsubscribe}")
    urls = re.findall(r"<([^>]+)>", list_unsubscribe)
    https_urls = [url for url in urls if url.startswith("https://")]

    if not https_urls:
        print(
            f"[Unsubscribe] No HTTPS URLs found in List-Unsubscribe header (found: {urls})"
        )
        logger.info("No HTTPS URLs found in List-Unsubscribe header")
        return None, False

    unsubscribe_url = https_urls[0]
    has_one_click = list_unsubscribe_post.strip() == "List-Unsubscribe=One-Click"

    print(f"[Unsubscribe] Found unsubscribe URL: {unsubscribe_url}")
    print(f"[Unsubscribe] List-Unsubscribe-Post header: {list_unsubscribe_post}")
    print(f"[Unsubscribe] One-click supported: {has_one_click}")
    logger.info(f"Found unsubscribe URL: {unsubscribe_url}, one-click: {has_one_click}")

    return unsubscribe_url, has_one_click


def attempt_one_click_unsubscribe(http_client, url: str) -> Tuple[bool, str]:
    print(f"[Unsubscribe] Attempting one-click unsubscribe via POST to: {url}")
    logger.info(f"Attempting one-click unsubscribe: {url}")
    try:
        response = http_client.post(
            url,
            data="List-Unsubscribe=One-Click",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
            follow_redirects=True,
        )
        print(f"[Unsubscribe] One-click POST response status: {response.status_code}")
        logger.info(f"One-click unsubscribe response status: {response.status_code}")
        if response.status_code in (200, 202, 204):
            msg = f"One-click unsubscribe successful (status {response.status_code})"
            print(f"[Unsubscribe] ✓ {msg}")
            return True, msg
        msg = f"One-click unsubscribe returned status {response.status_code}"
        print(f"[Unsubscribe] ✗ {msg}")
        return False, msg
    except Exception as e:
        error_msg = f"One-click unsubscribe error: {str(e)}"
        print(f"[Unsubscribe] ✗ {error_msg}")
        logger.warning(f"One-click unsubscribe failed for {url}: {e}")
        return False, error_msg


def attempt_form_unsubscribe(http_client, unsubscribe_url: str) -> Tuple[bool, str]:
    print(
        f"[Unsubscribe] Attempting form-based unsubscribe, fetching page: {unsubscribe_url}"
    )
    logger.info(f"Attempting form-based unsubscribe: {unsubscribe_url}")
    try:
        response = http_client.get(unsubscribe_url, timeout=10.0, follow_redirects=True)
        print(f"[Unsubscribe] GET response status: {response.status_code}")
        logger.info(f"Unsubscribe page fetch status: {response.status_code}")
        if response.status_code != 200:
            msg = f"Failed to fetch unsubscribe page (status {response.status_code})"
            print(f"[Unsubscribe] ✗ {msg}")
            return False, msg

        soup = BeautifulSoup(response.text, "html.parser")
        forms = soup.find_all("form")
        print(f"[Unsubscribe] Found {len(forms)} form(s) on page")

        unsubscribe_form = None
        for i, form in enumerate(forms):
            action = form.get("action", "").lower()
            form_text = form.get_text().lower()
            print(
                f"[Unsubscribe] Form {i+1}: action='{action}', text contains 'unsubscribe': {'unsubscribe' in form_text}"
            )
            if "unsubscribe" in action or "unsubscribe" in form_text:
                unsubscribe_form = form
                print(f"[Unsubscribe] Selected form {i+1} as unsubscribe form")
                break

        if not unsubscribe_form:
            msg = "No unsubscribe form found on page"
            print(f"[Unsubscribe] ✗ {msg}")
            logger.warning(msg)
            return False, msg

        form_action = unsubscribe_form.get("action", "")
        form_method = unsubscribe_form.get("method", "GET").upper()
        print(f"[Unsubscribe] Form action: '{form_action}', method: {form_method}")

        if form_action:
            if form_action.startswith("http"):
                submit_url = form_action
            elif form_action.startswith("/"):
                base_url = "/".join(unsubscribe_url.split("/")[:3])
                submit_url = urljoin(base_url, form_action)
            else:
                submit_url = urljoin(unsubscribe_url, form_action)
        else:
            submit_url = unsubscribe_url

        print(f"[Unsubscribe] Form submit URL: {submit_url}")

        form_data = {}
        for input_tag in unsubscribe_form.find_all("input"):
            input_type = input_tag.get("type", "text")
            input_name = input_tag.get("name", "")
            input_value = input_tag.get("value", "")

            if input_type in ("text", "email", "hidden") and input_name:
                form_data[input_name] = input_value
                print(f"[Unsubscribe] Form field: {input_name} = {input_value[:50]}...")

        print(
            f"[Unsubscribe] Submitting form with {len(form_data)} field(s) via {form_method}"
        )
        logger.info(
            f"Submitting form to {submit_url} with method {form_method}, fields: {list(form_data.keys())}"
        )

        if form_method == "POST":
            submit_response = http_client.post(
                submit_url, data=form_data, timeout=10.0, follow_redirects=True
            )
        else:
            submit_response = http_client.get(
                submit_url, params=form_data, timeout=10.0, follow_redirects=True
            )

        print(
            f"[Unsubscribe] Form submit response status: {submit_response.status_code}"
        )
        logger.info(f"Form submit response status: {submit_response.status_code}")

        submit_soup = BeautifulSoup(submit_response.text, "html.parser")
        response_text = submit_response.text.lower()
        response_title = ""
        title_tag = submit_soup.find("title")
        if title_tag:
            response_title = title_tag.get_text().lower()
            print(f"[Unsubscribe] Response page title: {title_tag.get_text()[:100]}")

        success_indicators = [
            "success",
            "unsubscribed",
            "confirmed",
            "removed",
            "updated",
        ]
        error_indicators = ["error", "failed", "invalid", "not found"]

        has_success = any(
            indicator in response_text or indicator in response_title
            for indicator in success_indicators
        )
        has_error = any(
            indicator in response_text or indicator in response_title
            for indicator in error_indicators
        )

        print(
            f"[Unsubscribe] Success indicators found: {has_success}, Error indicators found: {has_error}"
        )

        if (
            submit_response.status_code in (200, 202, 204)
            and has_success
            and not has_error
        ):
            msg = f"Form unsubscribe successful (status {submit_response.status_code})"
            print(f"[Unsubscribe] ✓ {msg}")
            return True, msg
        elif submit_response.status_code in (200, 202, 204):
            msg = f"Form submitted (status {submit_response.status_code}, success not confirmed)"
            print(f"[Unsubscribe] ? {msg}")
            return True, msg
        msg = f"Form unsubscribe returned status {submit_response.status_code}"
        print(f"[Unsubscribe] ✗ {msg}")
        return False, msg

    except Exception as e:
        error_msg = f"Form unsubscribe error: {str(e)}"
        print(f"[Unsubscribe] ✗ {error_msg}")
        logger.warning(f"Form unsubscribe failed for {unsubscribe_url}: {e}")
        return False, error_msg


def find_unsubscribe_links_in_html(html: str) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").lower()
        text = a.get_text().lower()
        if "unsubscribe" in href or "unsubscribe" in text:
            full_url = a.get("href")
            if full_url and full_url.startswith("http"):
                links.append(full_url)
    return links


def discover_unsubscribe_target(
    headers: dict, html: str
) -> Optional[UnsubscribeTarget]:
    unsubscribe_url, has_one_click = parse_list_unsubscribe(headers)
    if unsubscribe_url:
        return UnsubscribeTarget(
            url=unsubscribe_url, has_one_click=has_one_click, source="header_link"
        )

    html_links = find_unsubscribe_links_in_html(html)
    if html_links:
        return UnsubscribeTarget(
            url=html_links[0], has_one_click=False, source="body_link"
        )

    return None


def attempt_unsubscribe(
    http_client, target: UnsubscribeTarget, email_from: Optional[str] = None
) -> Tuple[str, str, Optional[str]]:
    status = "failed"
    method = target.source
    error = None

    try:
        if target.has_one_click:
            method = "one_click"
            success, msg = attempt_one_click_unsubscribe(http_client, target.url)
            if success:
                status = "success"
            else:
                status = "attempted"
                error = msg
        else:
            if target.source == "header_link":
                method = "header_link"
            elif target.source == "body_link":
                method = "body_link"
            else:
                method = "html_form"

            success, msg = attempt_form_unsubscribe(http_client, target.url)
            if success:
                status = "success"
            else:
                if "error:" in msg.lower() or "exception" in msg.lower():
                    status = "failed"
                elif "No unsubscribe form found" in msg or "Failed to fetch" in msg:
                    status = "manual_required"
                else:
                    status = "attempted"
                error = msg
    except Exception as e:
        error = str(e)
        status = "failed"
        logger.error(f"Unsubscribe exception: {e}", exc_info=True)

    return status, method, error


def best_effort_unsubscribe(http_client, headers: dict, html: str) -> Tuple[bool, str]:
    print("\n" + "=" * 70)
    print("[Unsubscribe] Starting unsubscribe process...")
    print("=" * 70)
    logger.info("Starting unsubscribe process")

    target = discover_unsubscribe_target(headers, html)
    if not target:
        msg = "No unsubscribe URL found"
        print(f"[Unsubscribe] ✗ {msg}")
        print("=" * 70 + "\n")
        return False, msg

    status, method, error = attempt_unsubscribe(http_client, target)
    print("=" * 70)
    if status == "success":
        print(f"[Unsubscribe] ✓ SUCCESS: {method}")
    else:
        print(f"[Unsubscribe] ✗ FAILED: {status} - {error or 'Unknown error'}")
    print("=" * 70 + "\n")
    return status == "success", error or f"Status: {status}"

from __future__ import annotations
import json
import logging
import time
from datetime import datetime
from typing import Optional, List

import httpx
from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER
from sqlmodel import Session, select, func
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .settings import settings
from .db import init_db, get_session
from .models import User, GmailAccount, Category, EmailRecord
from .auth import get_current_user, SESSION_KEY
from .google_client import oauth_login, oauth_callback, build_gmail_service_from_enc
from google.auth.exceptions import RefreshError
from .crypto import encrypt_str
from .gmail_service import (
    extract_headers,
    extract_bodies,
    parse_internal_date_ms,
    list_message_ids,
    archive_message,
    trash_message,
)
from .ai import choose_category, summarize_email
from .unsubscribe_agent import best_effort_unsubscribe

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=False,
    session_cookie="jump_session",
    max_age=60 * 60 * 24 * 7,
)

templates = Environment(
    loader=FileSystemLoader(
        str(__import__("pathlib").Path(__file__).parent / "templates")
    ),
    autoescape=select_autoescape(["html", "xml"]),
)


def render(request: Request, name: str, **ctx) -> HTMLResponse:
    tpl = templates.get_template(name)
    return HTMLResponse(tpl.render(**ctx))


@app.on_event("startup")
def _startup():
    # Warn if SECRET_KEY is still the default value
    if settings.SECRET_KEY == "change-me":
        logger.warning(
            "SECRET_KEY is still the default value 'change-me'. "
            "This will cause OAuth state mismatch errors. "
            "Please set a proper SECRET_KEY in your .env file."
        )
        print(
            "WARNING: SECRET_KEY is still 'change-me'. "
            "This will cause OAuth failures. Set a proper SECRET_KEY in .env"
        )
    init_db()


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return render(
            request, "login.html", user=None, test_user=settings.GOOGLE_TEST_USER
        )

    gmail_accounts = session.exec(
        select(GmailAccount).where(GmailAccount.user_id == user.id)
    ).all()
    categories = session.exec(
        select(Category)
        .where(Category.user_id == user.id)
        .order_by(Category.created_at.desc())
    ).all()

    counts = {}
    if categories:
        rows = session.exec(
            select(EmailRecord.category_id, func.count(EmailRecord.id))
            .where(EmailRecord.category_id.in_([c.id for c in categories]))
            .where(EmailRecord.deleted_at.is_(None))
            .group_by(EmailRecord.category_id)
        ).all()
        counts = {cid: cnt for cid, cnt in rows}

    return render(
        request,
        "dashboard.html",
        user=user,
        gmail_accounts=gmail_accounts,
        categories=categories,
        counts=counts,
        flash=None,
    )


@app.get("/auth/google")
async def auth_google(request: Request):
    return await oauth_login(request)


@app.get(settings.GOOGLE_REDIRECT_PATH)
async def auth_google_callback(
    request: Request, session: Session = Depends(get_session)
):
    try:
        data = await oauth_callback(request)
    except ValueError as e:
        # Log the actual error for debugging
        logger.error(f"OAuth callback error: {e}")
        print(f"OAuth callback error: {e}")  # Also print to console for visibility
        # OAuth error (e.g., state mismatch) - redirect to home
        # Check: SECRET_KEY, redirect_uri matches Google Console, session cookies enabled
        return RedirectResponse("/?error=oauth_failed", status_code=HTTP_303_SEE_OTHER)
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected OAuth error: {e}", exc_info=True)
        print(f"Unexpected OAuth error: {e}")
        return RedirectResponse("/?error=oauth_failed", status_code=HTTP_303_SEE_OTHER)

    token = data["token"]
    userinfo = data["userinfo"]
    email = userinfo.get("email")
    if not email:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    # Check if refresh_token is present in the token
    refresh_token = token.get("refresh_token")

    if refresh_token:
        logger.info(f"✓ Refresh token received for {email}")
        print(f"✓ Successfully authenticated {email} with refresh token")
    else:
        logger.warning(
            f"Token missing refresh_token for {email}. Token keys: {list(token.keys())}"
        )
        print(
            f"⚠ WARNING: Token for {email} is missing refresh_token. This may cause sync issues."
        )
        print(f"Token contains keys: {list(token.keys())}")

        # If refresh_token_expires_in exists but refresh_token doesn't, user needs to revoke
        if "refresh_token_expires_in" in token:
            print(
                "\nNOTE: Google returned refresh_token_expires_in but no refresh_token.\n"
                "This means the app was already authorized. To get refresh_token:\n"
                "1. Go to https://myaccount.google.com/permissions\n"
                "2. Find this app and click 'Remove' or 'Revoke Access'\n"
                "3. Clear browser cookies for localhost:8000\n"
                "4. Sign in again - this will return refresh_token\n"
            )
        else:
            print(
                "\nNo refresh_token received. This might happen if:\n"
                "1. The OAuth app configuration doesn't allow offline access\n"
                "2. The user hasn't granted full consent\n"
                "3. Google didn't return refresh_token for this authorization\n"
                "\nThe token will work until it expires, then re-authentication will be needed.\n"
            )

    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        user = User(email=email)
        session.add(user)
        session.commit()
        session.refresh(user)

    # Check if GmailAccount already exists for this user/email
    existing_ga = session.exec(
        select(GmailAccount).where(
            GmailAccount.user_id == user.id, GmailAccount.email == email
        )
    ).first()

    if existing_ga:
        # Update existing account with new token
        existing_ga.token_json_enc = encrypt_str(json.dumps(token))
        session.add(existing_ga)
        session.commit()
    else:
        # Create new account
        token_enc = encrypt_str(json.dumps(token))
        ga = GmailAccount(user_id=user.id, email=email, token_json_enc=token_enc)
        session.add(ga)
        session.commit()

    request.session[SESSION_KEY] = email
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.get("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.get("/categories/new", response_class=HTMLResponse)
def category_new(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    return render(request, "category_new.html", user=user, flash=None)


@app.post("/categories/new")
def category_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(...),
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    c = Category(user_id=user.id, name=name.strip(), description=description.strip())
    session.add(c)
    session.commit()
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.post("/sync")
def sync_now(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    gmail_accounts = session.exec(
        select(GmailAccount).where(GmailAccount.user_id == user.id)
    ).all()
    categories = session.exec(select(Category).where(Category.user_id == user.id)).all()

    # Very simple sync: for each account, search inbox with SYNC_QUERY, import up to 50.
    for ga in gmail_accounts:
        try:
            gmail, updated_token_enc = build_gmail_service_from_enc(ga.token_json_enc)
            ga.token_json_enc = updated_token_enc
        except ValueError as e:
            # Missing required token fields - user needs to re-authenticate
            logger.error(f"Gmail account {ga.email} token error: {e}")
            print(f"Error with Gmail account {ga.email}: {e}. Please re-authenticate.")
            continue

        try:
            ids = list_message_ids(gmail, "me", settings.SYNC_QUERY, max_results=50)
        except RefreshError as e:
            # Specific handling for refresh token errors
            logger.error(f"Gmail API refresh error for {ga.email}: {e}")
            print(
                f"Authentication error for {ga.email}: {e}. Please sign in with Google again."
            )
            continue
        except TypeError as e:
            # Handle datetime comparison errors
            if "datetime" in str(e).lower() or "offset" in str(e).lower():
                logger.error(f"Gmail API datetime error for {ga.email}: {e}")
                print(
                    f"Token expiry error for {ga.email}. "
                    "Please sign out and sign in again to refresh your token."
                )
            else:
                logger.error(f"Gmail API TypeError for {ga.email}: {e}")
                print(f"Error syncing emails for {ga.email}: {e}")
            continue
        except Exception as e:
            # Catch other Gmail API errors
            error_msg = str(e)
            if (
                "Bearer" in error_msg
                or "header" in error_msg.lower()
                or "illegal header" in error_msg.lower()
            ):
                logger.error(
                    f"Gmail API authentication header error for {ga.email}: {e}"
                )
                print(
                    f"Authentication error for {ga.email}: Invalid token. "
                    "Please sign out and sign in again."
                )
            else:
                logger.error(f"Gmail API error for {ga.email}: {e}")
                print(f"Error syncing emails for {ga.email}: {e}")
            continue
        # Process emails in batches to reduce database lock contention
        batch_size = 5
        email_records = []
        batch = []

        for idx, mid in enumerate(ids, 1):
            try:
                # Use no_autoflush to prevent autoflush during query
                # This avoids database lock issues when checking for existing records
                with session.no_autoflush:
                    existing = session.exec(
                        select(EmailRecord).where(
                            EmailRecord.gmail_account_id == ga.id,
                            EmailRecord.gmail_message_id == mid,
                        )
                    ).first()
                if existing:
                    continue

                full = (
                    gmail.users()
                    .messages()
                    .get(userId="me", id=mid, format="full")
                    .execute()
                )
                headers = extract_headers(full)
                subject = headers.get("subject", "")
                from_email = headers.get("from", "")
                snippet = full.get("snippet", "")
                body_text, body_html = extract_bodies(full)
                received_at = parse_internal_date_ms(full)

                chosen = choose_category(categories, subject, snippet, body_text or "")
                category_id = None
                if chosen:
                    match = next((c for c in categories if c.name == chosen), None)
                    category_id = match.id if match else None

                summary = summarize_email(
                    subject, from_email, body_text or snippet or ""
                )

                rec = EmailRecord(
                    gmail_account_id=ga.id,
                    category_id=category_id,
                    gmail_message_id=mid,
                    thread_id=full.get("threadId"),
                    from_email=from_email,
                    subject=subject,
                    snippet=snippet,
                    body_text=body_text,
                    body_html=body_html,
                    summary=summary,
                    received_at=received_at,
                    archived_at=datetime.utcnow(),
                )
                session.add(rec)
                batch.append((gmail, mid))  # Store for archiving later

                # Commit in batches to reduce lock contention
                if len(batch) >= batch_size:
                    try:
                        session.commit()
                        email_records.extend(batch)
                        batch = []  # Clear batch after successful commit
                    except Exception as db_error:
                        session.rollback()
                        error_msg = str(db_error)
                        if (
                            "locked" in error_msg.lower()
                            or "database is locked" in error_msg.lower()
                            or "autoflush" in error_msg.lower()
                        ):
                            logger.warning(
                                "Database locked during batch commit. Retrying after delay..."
                            )
                            # Wait a bit and retry once
                            time.sleep(1.0)  # Longer wait for lock
                            try:
                                session.commit()
                                email_records.extend(batch)
                                batch = []
                            except Exception as retry_error:
                                logger.error(
                                    f"Database still locked after retry: {retry_error}. Skipping batch."
                                )
                                # Clear batch to avoid re-adding
                                batch = []
                                # Continue processing - don't fail entire sync
                        else:
                            logger.error(
                                f"Database error during batch commit: {db_error}"
                            )
                            # Clear batch to avoid re-adding
                            batch = []
                            # Continue processing - don't fail entire sync

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error processing email {mid}: {e}")
                # Rollback and continue with next email
                try:
                    session.rollback()
                except Exception:
                    pass  # Ignore rollback errors
                continue

        # Commit any remaining records in the batch
        if batch:
            try:
                session.commit()
                email_records.extend(batch)
            except Exception as db_error:
                session.rollback()
                error_msg = str(db_error)
                if (
                    "locked" in error_msg.lower()
                    or "database is locked" in error_msg.lower()
                    or "autoflush" in error_msg.lower()
                ):
                    logger.warning("Database locked during final commit. Retrying...")
                    time.sleep(1.0)
                    try:
                        session.commit()
                        email_records.extend(batch)
                    except Exception:
                        logger.error("Failed to commit remaining batch after retry")
                else:
                    logger.error("Database error during final commit: %s", db_error)

        # Archive emails in Gmail after successful database commits
        for gmail_service, message_id in email_records:
            try:
                archive_message(gmail_service, "me", message_id)
            except Exception as archive_error:
                logger.warning(f"Failed to archive email {message_id}: {archive_error}")
                # Don't fail the whole sync if archiving fails

        ga.last_sync_at = datetime.utcnow()
        session.add(ga)
        session.commit()

    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.get("/categories/{category_id}", response_class=HTMLResponse)
def category_detail(
    category_id: int, request: Request, session: Session = Depends(get_session)
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    category = session.get(Category, category_id)
    if not category or category.user_id != user.id:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    emails = session.exec(
        select(EmailRecord)
        .where(EmailRecord.category_id == category_id)
        .where(EmailRecord.deleted_at.is_(None))
        .order_by(EmailRecord.received_at.desc().nullslast())
        .limit(200)
    ).all()

    return render(
        request,
        "category_detail.html",
        user=user,
        category=category,
        emails=emails,
        flash=None,
    )


@app.post("/categories/{category_id}/bulk")
def category_bulk(
    category_id: int,
    request: Request,
    action: str = Form(...),
    email_ids: Optional[List[int]] = Form(None),
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    email_ids = email_ids or []
    if not email_ids:
        return RedirectResponse(
            f"/categories/{category_id}", status_code=HTTP_303_SEE_OTHER
        )

    category = session.get(Category, category_id)
    if not category or category.user_id != user.id:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    # Pick first Gmail account for actions (records store gmail_account_id)
    for eid in email_ids:
        rec = session.get(EmailRecord, eid)
        if not rec or rec.category_id != category_id:
            continue
        ga = session.get(GmailAccount, rec.gmail_account_id)
        if not ga:
            continue
        gmail, updated_token_enc = build_gmail_service_from_enc(ga.token_json_enc)
        ga.token_json_enc = updated_token_enc
        session.add(ga)
        session.commit()

        if action == "delete":
            trash_message(gmail, "me", rec.gmail_message_id)
            rec.deleted_at = datetime.utcnow()
            session.add(rec)
            session.commit()

        elif action == "unsubscribe":
            full = (
                gmail.users()
                .messages()
                .get(userId="me", id=rec.gmail_message_id, format="full")
                .execute()
            )
            headers = extract_headers(full)
            body_text, body_html = extract_bodies(full)
            with httpx.Client() as client:
                ok, msg = best_effort_unsubscribe(client, headers, body_html or "")
            if ok:
                rec.unsubscribed_at = datetime.utcnow()
            # Store note in summary tail (simple)
            rec.summary = (rec.summary or "") + f"\n\n[Unsubscribe] {msg}"
            session.add(rec)
            session.commit()

    return RedirectResponse(
        f"/categories/{category_id}", status_code=HTTP_303_SEE_OTHER
    )


@app.get("/emails/{email_id}", response_class=HTMLResponse)
def email_detail(
    email_id: int, request: Request, session: Session = Depends(get_session)
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    rec = session.get(EmailRecord, email_id)
    if not rec:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    category = session.get(Category, rec.category_id) if rec.category_id else None
    if category and category.user_id != user.id:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    return render(
        request,
        "email_detail.html",
        user=user,
        email=rec,
        category_id=rec.category_id or 0,
        flash=None,
    )

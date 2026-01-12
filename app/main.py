from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Optional, List
from urllib.parse import quote

import httpx
from fastapi import FastAPI, Request, Depends, Form, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_303_SEE_OTHER
from sqlmodel import Session, select, func
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .settings import settings
from .db import init_db, get_session
from .models import User, GmailAccount, Category, EmailRecord
from .auth import (
    get_current_user,
    SESSION_KEY,
    get_active_gmail_account,
    ACTIVE_GMAIL_KEY,
)
from .google_client import oauth_login, oauth_callback, build_gmail_service_from_enc
from google.auth.exceptions import RefreshError
from .crypto import encrypt_str
from .gmail_service import (
    extract_headers,
    extract_bodies,
    list_message_ids,
    trash_message,
)
from .unsubscribe_agent import (
    discover_unsubscribe_target,
    attempt_unsubscribe,
    UnsubscribeTarget,
)
from .gmail_watch import setup_gmail_watch
from .history_sync import sync_history
from .email_processor import process_email_messages
from .pubsub_webhook import verify_pubsub_jwt, parse_pubsub_message

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)

try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception:
    pass

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


def get_or_create_uncategorized(
    session: Session, user: User, gmail_account: GmailAccount
) -> Category:
    existing = session.exec(
        select(Category).where(
            Category.user_id == user.id,
            Category.gmail_account_id == gmail_account.id,
            Category.name == "Uncategorized",
            Category.is_system.is_(True),
        )
    ).first()
    if existing:
        return existing
    uncategorized = Category(
        user_id=user.id,
        gmail_account_id=gmail_account.id,
        name="Uncategorized",
        description="Emails not categorized yet",
        is_system=True,
    )
    session.add(uncategorized)
    session.commit()
    session.refresh(uncategorized)
    return uncategorized


@app.on_event("startup")
def _startup():
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

    active_gmail = get_active_gmail_account(request, session, user)
    if not active_gmail:
        return render(
            request,
            "dashboard.html",
            user=user,
            gmail_accounts=gmail_accounts,
            active_gmail_id=None,
            categories=[],
            counts={},
            flash=None,
        )

    categories = session.exec(
        select(Category)
        .where(Category.gmail_account_id == active_gmail.id)
        .order_by(Category.is_system.asc(), Category.created_at.desc())
    ).all()

    uncategorized = get_or_create_uncategorized(session, user, active_gmail)
    if uncategorized.id not in [c.id for c in categories]:
        categories.insert(0, uncategorized)

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
        active_gmail_id=active_gmail.id,
        categories=categories,
        counts=counts,
        flash=None,
    )


@app.get("/auth/google")
async def auth_google(request: Request):
    mode = request.query_params.get("mode", "login")
    request.session["oauth_mode"] = mode
    return await oauth_login(request, prompt="consent")


@app.get(settings.GOOGLE_REDIRECT_PATH)
async def auth_google_callback(
    request: Request, session: Session = Depends(get_session)
):
    try:
        data = await oauth_callback(request)
    except ValueError as e:
        logger.error(f"OAuth callback error: {e}")
        print(f"OAuth callback error: {e}")
        return RedirectResponse("/?error=oauth_failed", status_code=HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Unexpected OAuth error: {e}", exc_info=True)
        print(f"Unexpected OAuth error: {e}")
        return RedirectResponse("/?error=oauth_failed", status_code=HTTP_303_SEE_OTHER)

    token = data["token"]
    userinfo = data["userinfo"]
    email = userinfo.get("email")
    if not email:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    oauth_mode = request.session.pop("oauth_mode", "login")

    if oauth_mode == "connect":
        user = get_current_user(request, session)
        if not user:
            return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

        existing_ga = session.exec(
            select(GmailAccount).where(
                GmailAccount.user_id == user.id, GmailAccount.email == email
            )
        ).first()

        if existing_ga:
            existing_ga.token_json_enc = encrypt_str(json.dumps(token))
            session.add(existing_ga)
            session.commit()
            session.refresh(existing_ga)
            ga = existing_ga
        else:
            token_enc = encrypt_str(json.dumps(token))
            ga = GmailAccount(user_id=user.id, email=email, token_json_enc=token_enc)
            session.add(ga)
            session.commit()
            session.refresh(ga)

        try:
            gmail, updated_token_enc = build_gmail_service_from_enc(ga.token_json_enc)
            ga.token_json_enc = updated_token_enc
            session.add(ga)
            session.commit()
            setup_gmail_watch(gmail, ga, session)
        except Exception as e:
            logger.warning(f"Failed to setup Gmail watch during OAuth callback: {e}")

        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

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

    existing_ga = session.exec(
        select(GmailAccount).where(
            GmailAccount.user_id == user.id, GmailAccount.email == email
        )
    ).first()

    if existing_ga:
        existing_ga.token_json_enc = encrypt_str(json.dumps(token))
        session.add(existing_ga)
        session.commit()
        session.refresh(existing_ga)
        ga = existing_ga
    else:
        token_enc = encrypt_str(json.dumps(token))
        ga = GmailAccount(user_id=user.id, email=email, token_json_enc=token_enc)
        session.add(ga)
        session.commit()
        session.refresh(ga)

    try:
        gmail, updated_token_enc = build_gmail_service_from_enc(ga.token_json_enc)
        ga.token_json_enc = updated_token_enc
        session.add(ga)
        session.commit()
        setup_gmail_watch(gmail, ga, session)
    except Exception as e:
        logger.warning(f"Failed to setup Gmail watch during OAuth callback: {e}")

    request.session[SESSION_KEY] = email
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.get("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.post("/accounts/{account_id}/select")
def select_account(
    account_id: int, request: Request, session: Session = Depends(get_session)
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    gmail_account = session.get(GmailAccount, account_id)
    if not gmail_account or gmail_account.user_id != user.id:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    request.session[ACTIVE_GMAIL_KEY] = account_id
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.post("/accounts/{account_id}/disconnect")
def disconnect_account(
    account_id: int, request: Request, session: Session = Depends(get_session)
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    gmail_account = session.get(GmailAccount, account_id)
    if not gmail_account or gmail_account.user_id != user.id:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    if request.session.get(ACTIVE_GMAIL_KEY) == account_id:
        del request.session[ACTIVE_GMAIL_KEY]

    email_records = session.exec(
        select(EmailRecord).where(EmailRecord.gmail_account_id == account_id)
    ).all()
    email_count = len(email_records)

    for email_record in email_records:
        email_record.category_id = None
        session.add(email_record)
    session.commit()

    categories = session.exec(
        select(Category).where(Category.gmail_account_id == account_id)
    ).all()
    for category in categories:
        session.delete(category)

    for email_record in email_records:
        session.delete(email_record)

    session.delete(gmail_account)
    session.commit()

    logger.info(
        f"Disconnected Gmail account {gmail_account.email} for user {user.email}. "
        f"Deleted {email_count} email records."
    )

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

    active_gmail = get_active_gmail_account(request, session, user)
    if not active_gmail:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    c = Category(
        user_id=user.id,
        gmail_account_id=active_gmail.id,
        name=name.strip(),
        description=description.strip(),
    )
    session.add(c)
    session.commit()
    return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)


@app.post("/sync")
def sync_now(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    active_gmail = get_active_gmail_account(request, session, user)
    if not active_gmail:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    categories = session.exec(
        select(Category).where(Category.gmail_account_id == active_gmail.id)
    ).all()

    ga = active_gmail
    try:
        gmail, updated_token_enc = build_gmail_service_from_enc(ga.token_json_enc)
        ga.token_json_enc = updated_token_enc
    except ValueError as e:
        logger.error(f"Gmail account {ga.email} token error: {e}")
        print(f"Error with Gmail account {ga.email}: {e}. Please re-authenticate.")
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    try:
        ids = list_message_ids(gmail, "me", settings.SYNC_QUERY, max_results=25)
    except RefreshError as e:
        logger.error(f"Gmail API refresh error for {ga.email}: {e}")
        print(
            f"Authentication error for {ga.email}: {e}. Please sign in with Google again."
        )
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    except TypeError as e:
        if "datetime" in str(e).lower() or "offset" in str(e).lower():
            logger.error(f"Gmail API datetime error for {ga.email}: {e}")
            print(
                f"Token expiry error for {ga.email}. "
                "Please sign out and sign in again to refresh your token."
            )
        else:
            logger.error(f"Gmail API TypeError for {ga.email}: {e}")
            print(f"Error syncing emails for {ga.email}: {e}")
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)
    except Exception as e:
        error_msg = str(e)
        if (
            "Bearer" in error_msg
            or "header" in error_msg.lower()
            or "illegal header" in error_msg.lower()
        ):
            logger.error(f"Gmail API authentication header error for {ga.email}: {e}")
            print(
                f"Authentication error for {ga.email}: Invalid token. "
                "Please sign out and sign in again."
            )
        else:
            logger.error(f"Gmail API error for {ga.email}: {e}")
            print(f"Error syncing emails for {ga.email}: {e}")
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    uncategorized = get_or_create_uncategorized(session, user, ga)
    if uncategorized.id not in [c.id for c in categories]:
        categories.append(uncategorized)

    process_email_messages(
        gmail, ga, ids, categories, session, user, get_or_create_uncategorized
    )

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

    active_gmail = get_active_gmail_account(request, session, user)
    if not active_gmail:
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    category = session.get(Category, category_id)
    if (
        not category
        or category.user_id != user.id
        or category.gmail_account_id != active_gmail.id
    ):
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    emails = session.exec(
        select(EmailRecord)
        .where(EmailRecord.category_id == category_id)
        .where(EmailRecord.deleted_at.is_(None))
        .order_by(EmailRecord.received_at.desc().nullslast())
        .limit(200)
    ).all()

    unsubscribe_started = request.query_params.get("unsubscribe_started") == "true"

    return render(
        request,
        "category_detail.html",
        user=user,
        category=category,
        emails=emails,
        unsubscribe_started=unsubscribe_started,
        flash=None,
    )


def process_unsubscribe_background(email_id: int, category_id: int):
    from .db import engine

    with Session(engine) as session:
        try:
            rec = session.get(EmailRecord, email_id)
            if not rec or rec.category_id != category_id:
                return

            ga = session.get(GmailAccount, rec.gmail_account_id)
            if not ga:
                return

            logger.info(
                f"Processing unsubscribe for email {rec.id} from {rec.from_email}"
            )
            print(
                f"\n[Unsubscribe] Processing unsubscribe for email ID {rec.id} from {rec.from_email}"
            )

            try:
                gmail, updated_token_enc = build_gmail_service_from_enc(
                    ga.token_json_enc
                )
                ga.token_json_enc = updated_token_enc
                session.add(ga)
                session.commit()

                msg = (
                    gmail.users()
                    .messages()
                    .get(
                        userId="me",
                        id=rec.gmail_message_id,
                        format="metadata",
                        metadataHeaders=["List-Unsubscribe", "List-Unsubscribe-Post"],
                    )
                    .execute()
                )
                headers = extract_headers(msg)
                body_html = rec.body_html

                if not headers.get("list-unsubscribe") and not body_html:
                    full = (
                        gmail.users()
                        .messages()
                        .get(userId="me", id=rec.gmail_message_id, format="full")
                        .execute()
                    )
                    headers = extract_headers(full)
                    body_text, body_html = extract_bodies(full)

                print(
                    f"[Unsubscribe] Extracted headers, found {len(headers)} header(s)"
                )

                target = discover_unsubscribe_target(headers, body_html or "")

                if not target:
                    rec.unsubscribe_status = "failed"
                    rec.unsubscribe_method = None
                    rec.unsubscribe_url = None
                    rec.unsubscribe_error = "No unsubscribe URL found"
                    session.add(rec)
                    session.commit()
                    logger.warning(f"No unsubscribe target found for email {rec.id}")
                    return

                rec.unsubscribe_url = target.url
                session.add(rec)
                session.commit()

                with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}) as client:
                    status, method, error = attempt_unsubscribe(
                        client, target, rec.from_email
                    )

                rec.unsubscribe_status = status
                rec.unsubscribe_method = method
                rec.unsubscribe_error = error

                if status == "success":
                    rec.unsubscribed_at = datetime.utcnow()
                    logger.info(f"Unsubscribe successful for email {rec.id}: {method}")
                    print(
                        f"[Unsubscribe] ✓ Successfully unsubscribed! Method: {method}, Timestamp: {rec.unsubscribed_at}"
                    )
                else:
                    logger.warning(f"Unsubscribe {status} for email {rec.id}: {error}")
                    print(
                        f"[Unsubscribe] Status: {status}, Method: {method}, Error: {error}"
                    )

                session.add(rec)
                session.commit()
            except Exception as e:
                error_msg = f"Error during unsubscribe: {str(e)}"
                logger.error(
                    f"Unsubscribe error for email {rec.id}: {e}", exc_info=True
                )
                print(f"[Unsubscribe] ✗ ERROR: {error_msg}")
                rec.unsubscribe_status = "failed"
                rec.unsubscribe_error = error_msg
                session.add(rec)
                session.commit()
        except Exception as e:
            logger.error(
                f"Background unsubscribe task error for email {email_id}: {e}",
                exc_info=True,
            )


@app.post("/categories/{category_id}/bulk")
def category_bulk(
    category_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
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

    if action == "delete":
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
            trash_message(gmail, "me", rec.gmail_message_id)
            rec.deleted_at = datetime.utcnow()
            session.add(rec)
            session.commit()

    elif action == "unsubscribe":
        for eid in email_ids:
            background_tasks.add_task(process_unsubscribe_background, eid, category_id)
        return RedirectResponse(
            f"/categories/{category_id}?unsubscribe_started=true",
            status_code=HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        f"/categories/{category_id}", status_code=HTTP_303_SEE_OTHER
    )


@app.get("/api/categories/{category_id}/unsubscribe-status")
def get_unsubscribe_status(
    category_id: int, request: Request, session: Session = Depends(get_session)
):
    user = get_current_user(request, session)
    if not user:
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)

    category = session.get(Category, category_id)
    if not category or category.user_id != user.id:
        return JSONResponse(content={"error": "Not found"}, status_code=404)

    emails = session.exec(
        select(EmailRecord)
        .where(EmailRecord.category_id == category_id)
        .where(EmailRecord.deleted_at.is_(None))
        .order_by(EmailRecord.received_at.desc().nullslast())
        .limit(200)
    ).all()

    statuses = []
    for e in emails:
        if e.unsubscribe_status or e.unsubscribed_at:
            statuses.append(
                {
                    "id": e.id,
                    "unsubscribe_status": e.unsubscribe_status,
                    "unsubscribe_method": e.unsubscribe_method,
                    "unsubscribe_url": e.unsubscribe_url,
                    "unsubscribe_error": e.unsubscribe_error,
                    "unsubscribed_at": (
                        e.unsubscribed_at.isoformat() if e.unsubscribed_at else None
                    ),
                }
            )

    return JSONResponse(content={"statuses": statuses})


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


@app.post("/webhooks/pubsub")
async def pubsub_webhook(request: Request, session: Session = Depends(get_session)):
    if not verify_pubsub_jwt(request):
        raise HTTPException(status_code=401, detail="Invalid JWT token")

    try:
        body = await request.json()
        data = parse_pubsub_message(body)
        if not data:
            logger.warning("Failed to parse Pub/Sub message data")
            return Response(status_code=200)

        email_address = data.get("emailAddress")
        history_id = data.get("historyId")

        if not email_address:
            logger.warning("Missing emailAddress in Pub/Sub message")
            return Response(status_code=200)

        gmail_account = session.exec(
            select(GmailAccount).where(GmailAccount.email == email_address)
        ).first()

        if not gmail_account:
            logger.warning(f"No GmailAccount found for {email_address}")
            return Response(status_code=200)

        if not gmail_account.last_history_id:
            logger.warning(
                f"No last_history_id for {gmail_account.email}, skipping history sync"
            )
            return Response(status_code=200)

        try:
            gmail, updated_token_enc = build_gmail_service_from_enc(
                gmail_account.token_json_enc
            )
            gmail_account.token_json_enc = updated_token_enc
            session.add(gmail_account)
            session.commit()
        except Exception as e:
            logger.error(f"Failed to build Gmail service for {email_address}: {e}")
            return Response(status_code=200)

        user = session.get(User, gmail_account.user_id)
        if not user:
            logger.warning(f"No User found for GmailAccount {gmail_account.id}")
            return Response(status_code=200)

        categories = session.exec(
            select(Category).where(Category.gmail_account_id == gmail_account.id)
        ).all()

        uncategorized = get_or_create_uncategorized(session, user, gmail_account)
        if uncategorized.id not in [c.id for c in categories]:
            categories.append(uncategorized)

        try:
            sync_history(
                gmail,
                gmail_account,
                gmail_account.last_history_id,
                categories,
                session,
                user,
                get_or_create_uncategorized,
            )
            if history_id:
                gmail_account.last_history_id = history_id
                session.add(gmail_account)
                session.commit()
        except Exception as e:
            logger.error(f"History sync error for {email_address}: {e}")

        return Response(status_code=200)

    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        return Response(status_code=200)

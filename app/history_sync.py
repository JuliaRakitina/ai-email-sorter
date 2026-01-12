from __future__ import annotations
import logging
from typing import List, Optional
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from sqlmodel import Session, select

from .models import GmailAccount, Category, User
from .gmail_service import list_message_ids
from .email_processor import process_email_messages
from .settings import settings

logger = logging.getLogger(__name__)


def sync_history(
    gmail_service: Resource,
    gmail_account: GmailAccount,
    start_history_id: str,
    categories: List[Category],
    session: Session,
    user: User,
    get_uncategorized_func,
) -> tuple[Optional[str], int]:
    try:
        history_response = (
            gmail_service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
                labelId="INBOX",
            )
            .execute()
        )

        message_ids = []
        new_history_id = start_history_id

        for history_record in history_response.get("history", []):
            messages_added = history_record.get("messagesAdded", [])
            for msg_added in messages_added:
                msg = msg_added.get("message", {})
                msg_id = msg.get("id")
                if msg_id:
                    message_ids.append(msg_id)

            new_history_id = history_record.get("historyId", new_history_id)

        processed_count = 0
        if message_ids:
            processed_count = process_email_messages(
                gmail_service,
                gmail_account,
                message_ids,
                categories,
                session,
                user,
                get_uncategorized_func,
            )
            logger.info(
                f"History sync processed {processed_count} emails for {gmail_account.email}"
            )

        gmail_account.last_history_id = new_history_id
        session.add(gmail_account)
        session.commit()

        return new_history_id, processed_count

    except HttpError as e:
        error_content = e.content.decode("utf-8") if e.content else ""
        if (
            "startHistoryId" in error_content.lower()
            or "invalid" in error_content.lower()
        ):
            logger.warning(
                f"Invalid startHistoryId for {gmail_account.email}, falling back to query sync"
            )
            return fallback_query_sync(
                gmail_service,
                gmail_account,
                categories,
                session,
                user,
                get_uncategorized_func,
            )
        raise
    except Exception as e:
        logger.error(f"History sync error for {gmail_account.email}: {e}")
        return None, 0


def fallback_query_sync(
    gmail_service: Resource,
    gmail_account: GmailAccount,
    categories: List[Category],
    session: Session,
    user: User,
    get_uncategorized_func,
) -> tuple[Optional[str], int]:
    try:
        ids = list_message_ids(
            gmail_service, "me", "in:inbox newer_than:1d", max_results=10
        )
        processed_count = 0
        if ids:
            processed_count = process_email_messages(
                gmail_service,
                gmail_account,
                ids,
                categories,
                session,
                user,
                get_uncategorized_func,
            )

        profile = gmail_service.users().getProfile(userId="me").execute()
        new_history_id = profile.get("historyId")
        if new_history_id:
            gmail_account.last_history_id = new_history_id
            session.add(gmail_account)
            session.commit()

        logger.info(
            f"Fallback query sync completed for {gmail_account.email}, "
            f"new historyId={new_history_id}, processed {processed_count} emails"
        )
        return new_history_id, processed_count
    except Exception as e:
        logger.error(f"Fallback query sync error for {gmail_account.email}: {e}")
        return None, 0

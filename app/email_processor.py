from __future__ import annotations
import logging
import time
from datetime import datetime
from typing import List, Tuple, Optional
from googleapiclient.discovery import Resource
from sqlmodel import Session, select

from .models import GmailAccount, Category, EmailRecord
from .gmail_service import (
    extract_headers,
    extract_bodies,
    parse_internal_date_ms,
    archive_message,
)
from .ai import choose_category, summarize_email

logger = logging.getLogger(__name__)


def process_email_messages(
    gmail_service: Resource,
    gmail_account: GmailAccount,
    message_ids: List[str],
    categories: List[Category],
    session: Session,
) -> int:
    batch_size = 5
    email_records = []
    batch = []
    processed = 0

    for idx, mid in enumerate(message_ids, 1):
        try:
            with session.no_autoflush:
                existing = session.exec(
                    select(EmailRecord).where(
                        EmailRecord.gmail_account_id == gmail_account.id,
                        EmailRecord.gmail_message_id == mid,
                    )
                ).first()
            if existing:
                continue

            full = (
                gmail_service.users()
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

            summary = summarize_email(subject, from_email, body_text or snippet or "")

            rec = EmailRecord(
                gmail_account_id=gmail_account.id,
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
            batch.append((gmail_service, mid))
            processed += 1

            if len(batch) >= batch_size:
                try:
                    session.commit()
                    email_records.extend(batch)
                    batch = []
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
                        time.sleep(1.0)
                        try:
                            session.commit()
                            email_records.extend(batch)
                            batch = []
                        except Exception as retry_error:
                            logger.error(
                                f"Database still locked after retry: {retry_error}. Skipping batch."
                            )
                            batch = []
                    else:
                        logger.error(f"Database error during batch commit: {db_error}")
                        batch = []

        except Exception as e:
            logger.error(f"Error processing email {mid}: {e}")
            try:
                session.rollback()
            except Exception:
                pass
            continue

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
                logger.error(f"Database error during final commit: {db_error}")

    for gmail_service, message_id in email_records:
        try:
            archive_message(gmail_service, "me", message_id)
        except Exception as archive_error:
            logger.warning(f"Failed to archive email {message_id}: {archive_error}")

    return processed


from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
from googleapiclient.discovery import Resource
from .settings import settings
from .models import GmailAccount
from sqlmodel import Session

logger = logging.getLogger(__name__)


def _get_topic_name() -> Optional[str]:
    topic_name = (
        settings.PUBSUB_TOPIC_NAME.strip() if settings.PUBSUB_TOPIC_NAME else ""
    )

    if not topic_name:
        return None

    if topic_name.startswith("projects/") and "/topics/" in topic_name:
        return topic_name

    project_id = settings.GCP_PROJECT_ID.strip() if settings.GCP_PROJECT_ID else ""
    if project_id and not topic_name.startswith("projects/"):
        return f"projects/{project_id}/topics/{topic_name}"

    return None


def setup_gmail_watch(
    gmail_service: Resource, gmail_account: GmailAccount, session: Session
) -> bool:
    topic_name = _get_topic_name()

    if not topic_name:
        logger.warning(
            "PUBSUB_TOPIC_NAME not configured or invalid. "
            "Set PUBSUB_TOPIC_NAME to 'projects/{project-id}/topics/{topic-id}' "
            "or set both GCP_PROJECT_ID and PUBSUB_TOPIC_NAME (topic name only)"
        )
        print(
            "WARNING: Gmail watch not configured. "
            "Set PUBSUB_TOPIC_NAME='projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME' in .env"
        )
        return False

    try:
        watch_request = {
            "topicName": topic_name,
            "labelIds": ["INBOX"],
            "labelFilterBehavior": "INCLUDE",
        }
        response = (
            gmail_service.users().watch(userId="me", body=watch_request).execute()
        )

        history_id = response.get("historyId")
        expiration_ms = response.get("expiration")

        if history_id:
            gmail_account.last_history_id = history_id
        if expiration_ms:
            expiration_ts = int(expiration_ms) / 1000
            gmail_account.watch_expiration = datetime.fromtimestamp(
                expiration_ts, tz=timezone.utc
            ).replace(tzinfo=None)
        gmail_account.watch_active = True

        session.add(gmail_account)
        session.commit()

        logger.info(
            f"Gmail watch setup successful for {gmail_account.email}, "
            f"historyId={history_id}, expires={gmail_account.watch_expiration}"
        )
        return True
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg and "not authorized" in error_msg.lower():
            logger.error(
                f"Gmail watch setup failed: Gmail API service account lacks permission "
                f"to publish to Pub/Sub topic '{topic_name}'. "
                f"Grant 'pubsub.topics.publish' permission to "
                f"'gmail-api-push@system.gserviceaccount.com' on the topic."
            )
            print(
                "\n" + "=" * 70 + "\n"
                "ERROR: Gmail API service account needs permission to publish to Pub/Sub topic.\n\n"
                "To fix this, run:\n"
                f"  gcloud pubsub topics add-iam-policy-binding {topic_name} \\\n"
                "    --member='serviceAccount:gmail-api-push@system.gserviceaccount.com' \\\n"
                "    --role='roles/pubsub.publisher'\n\n"
                "Or use GCP Console:\n"
                "  1. Go to Pub/Sub > Topics > YOUR_TOPIC_NAME\n"
                "  2. Click 'SHOW INFO PANEL' > 'PERMISSIONS' tab\n"
                "  3. Click 'ADD PRINCIPAL'\n"
                "  4. Principal: gmail-api-push@system.gserviceaccount.com\n"
                "  5. Role: Pub/Sub Publisher\n"
                "  6. Save\n" + "=" * 70 + "\n"
            )
        else:
            logger.error(f"Failed to setup Gmail watch for {gmail_account.email}: {e}")
        return False

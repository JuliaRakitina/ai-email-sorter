from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GmailAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    email: str = Field(index=True)
    token_json_enc: str
    last_sync_at: Optional[datetime] = None
    last_history_id: Optional[str] = None
    watch_expiration: Optional[datetime] = None
    watch_active: bool = Field(default=False)


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    gmail_account_id: int = Field(foreign_key="gmailaccount.id", index=True)
    name: str = Field(index=True)
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EmailRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    gmail_account_id: int = Field(foreign_key="gmailaccount.id", index=True)
    category_id: Optional[int] = Field(
        default=None, foreign_key="category.id", index=True
    )

    gmail_message_id: str = Field(index=True)
    thread_id: Optional[str] = None

    from_email: Optional[str] = None
    subject: Optional[str] = None
    snippet: Optional[str] = None

    body_text: Optional[str] = None
    body_html: Optional[str] = None

    summary: Optional[str] = None
    received_at: Optional[datetime] = None

    archived_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    unsubscribed_at: Optional[datetime] = None

from typing import Optional
from fastapi import Request
from sqlmodel import Session, select
from .models import User, GmailAccount

SESSION_KEY = "user_email"
ACTIVE_GMAIL_KEY = "active_gmail_account_id"

def get_current_user(request: Request, session: Session) -> Optional[User]:
    email = request.session.get(SESSION_KEY)
    if not email:
        return None
    return session.exec(select(User).where(User.email == email)).first()

def get_active_gmail_account(request: Request, session: Session, user: User) -> Optional[GmailAccount]:
    active_id = request.session.get(ACTIVE_GMAIL_KEY)
    if active_id:
        ga = session.get(GmailAccount, active_id)
        if ga and ga.user_id == user.id:
            return ga
    
    gmail_accounts = session.exec(
        select(GmailAccount).where(GmailAccount.user_id == user.id)
    ).all()
    if gmail_accounts:
        request.session[ACTIVE_GMAIL_KEY] = gmail_accounts[0].id
        return gmail_accounts[0]
    return None

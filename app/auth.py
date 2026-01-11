from typing import Optional
from fastapi import Request
from sqlmodel import Session, select
from .models import User

SESSION_KEY = "user_email"

def get_current_user(request: Request, session: Session) -> Optional[User]:
    email = request.session.get(SESSION_KEY)
    if not email:
        return None
    return session.exec(select(User).where(User.email == email)).first()

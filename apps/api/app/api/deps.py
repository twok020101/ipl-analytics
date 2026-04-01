"""FastAPI dependencies."""

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.auth import decode_token
from app.models.models import User


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    """Optional auth -- returns None if no token provided."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        user = db.get(User, int(payload["sub"]))
        return user
    except Exception:
        return None


def require_auth(authorization: str = Header(...), db: Session = Depends(get_db)) -> User:
    """Required auth -- raises 401 if not authenticated."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        user = db.get(User, int(payload["sub"]))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

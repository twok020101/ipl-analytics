"""FastAPI dependencies for auth, DB sessions, and role-based access control.

Role hierarchy: admin > analyst > viewer
- viewer:  read-only access to dashboards, stats, standings
- analyst: all viewer access + strategy, analysis, AI insights, predictions
- admin:   all analyst access + user management, org settings, cron triggers
"""

from collections.abc import Generator
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.auth import decode_token
from app.models.models import User, UserRole


# --- Role hierarchy (higher index = more privilege) ---
_ROLE_RANK = {
    UserRole.viewer: 0,
    UserRole.analyst: 1,
    UserRole.admin: 2,
}


def get_db() -> Generator:
    """Yield a SQLAlchemy session, auto-closed after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Optional auth — returns None if no valid token provided."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        user = db.get(User, int(payload["sub"]))
        return user
    except Exception:
        return None


def require_auth(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> User:
    """Required auth — raises 401 if not authenticated."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        user = db.get(User, int(payload["sub"]))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _require_role(minimum_role: UserRole, user: User) -> User:
    """Check that the authenticated user has at least `minimum_role` privilege.

    Called by the convenience dependencies below — not used as a FastAPI Depends.
    """
    user_rank = _ROLE_RANK.get(user.role, -1)
    required_rank = _ROLE_RANK.get(minimum_role, 99)
    if user_rank < required_rank:
        raise HTTPException(
            status_code=403,
            detail=f"Requires {minimum_role.value} role or higher",
        )
    return user


# --- Convenience dependencies for route-level role checks ---

def require_viewer(user: User = Depends(require_auth)) -> User:
    """Any authenticated user (viewer+) can access."""
    return _require_role(UserRole.viewer, user)


def require_analyst(user: User = Depends(require_auth)) -> User:
    """Analyst or admin can access — strategy, analysis, AI features."""
    return _require_role(UserRole.analyst, user)


def require_admin(user: User = Depends(require_auth)) -> User:
    """Admin only — user management, org settings, system operations."""
    return _require_role(UserRole.admin, user)

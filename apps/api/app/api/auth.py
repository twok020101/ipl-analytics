"""Authentication & user management API routes.

Public:  POST /register, POST /login
Auth:    GET /me
Admin:   GET /users, PATCH /users/{id}/role, PATCH /users/{id}/active,
         PATCH /users/{id}/org, POST /orgs, GET /orgs
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_db, require_auth, require_admin
from app.services.auth import register_user, authenticate_user
from app.models.models import User, UserRole, Organization, Team

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Request / Response schemas ---

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    organization: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RoleUpdateRequest(BaseModel):
    role: str  # "admin" | "analyst" | "viewer"


class ActiveUpdateRequest(BaseModel):
    is_active: bool


class OrgTeamLinkRequest(BaseModel):
    team_id: int  # IPL team ID to associate with this organization


class CreateOrgRequest(BaseModel):
    name: str
    team_id: Optional[int] = None  # Optionally link to an IPL team on creation


class MoveUserOrgRequest(BaseModel):
    organization_id: Optional[int] = None  # None = remove from org


def _user_dict(user: User) -> dict:
    """Serialize a User to a consistent JSON-safe dict."""
    org = user.organization
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "organization_id": user.organization_id,
        "organization_name": org.name if org else None,
        "is_active": user.is_active,
        "team_id": org.team_id if org else None,
        "team_name": org.team.short_name if org and org.team else None,
    }


# --- Public routes ---

@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user. First user in an org gets admin role."""
    try:
        user, token = register_user(db, req.email, req.password, req.name, req.organization)
        return {"token": token, "user": _user_dict(user)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and return JWT token."""
    try:
        user, token = authenticate_user(db, req.email, req.password)
        return {"token": token, "user": _user_dict(user)}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
def get_me(user: User = Depends(require_auth)):
    """Get current authenticated user profile."""
    return _user_dict(user)


# --- Admin-only user management ---

@router.get("/users")
def list_users(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all users in the admin's organization (or all users for super-admin)."""
    query = db.query(User)
    # Scope to admin's org unless they have no org (super-admin sees all)
    if user.organization_id:
        query = query.filter(User.organization_id == user.organization_id)
    users = query.order_by(User.id).all()
    return [_user_dict(u) for u in users]


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    req: RoleUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Change a user's role (admin only). Cannot demote yourself."""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Admins can only manage users in their own org
    if admin.organization_id and target.organization_id != admin.organization_id:
        raise HTTPException(status_code=403, detail="Cannot manage users outside your organization")

    # Prevent self-demotion (avoids orphaned orgs with no admin)
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    try:
        target.role = UserRole(req.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {req.role}")

    db.commit()
    return _user_dict(target)


@router.patch("/users/{user_id}/active")
def update_user_active(
    user_id: int,
    req: ActiveUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Enable or disable a user account (admin only)."""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if admin.organization_id and target.organization_id != admin.organization_id:
        raise HTTPException(status_code=403, detail="Cannot manage users outside your organization")

    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    target.is_active = req.is_active
    db.commit()
    return _user_dict(target)


@router.patch("/org/team")
def link_org_to_team(
    req: OrgTeamLinkRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Link the admin's organization to an IPL team for scoped dashboards.

    Once linked, all users in this org will see a team-specific dashboard
    with analysis, game plans, and strategy tailored to their team.
    """
    if not admin.organization_id:
        raise HTTPException(status_code=400, detail="You must belong to an organization")

    team = db.get(Team, req.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    org = db.get(Organization, admin.organization_id)
    org.team_id = req.team_id
    db.commit()

    return {
        "organization": org.name,
        "team_id": team.id,
        "team_name": team.name,
        "short_name": team.short_name,
    }


def _org_dict(org: Organization) -> dict:
    """Serialize an Organization to a JSON-safe dict."""
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan.value if hasattr(org.plan, "value") else org.plan,
        "team_id": org.team_id,
        "team_name": org.team.short_name if org.team else None,
        "user_count": len(org.users) if org.users else 0,
    }


# --- Organization management (admin / super-admin) ---

@router.get("/orgs")
def list_organizations(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List organizations. Super-admins (no org) see all; org admins see only their own."""
    if admin.organization_id:
        org = db.get(Organization, admin.organization_id)
        return [_org_dict(org)] if org else []
    # Super-admin: list all orgs
    orgs = db.query(Organization).order_by(Organization.id).all()
    return [_org_dict(o) for o in orgs]


@router.post("/orgs")
def create_organization(
    req: CreateOrgRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new organization (admin only).

    Super-admins can create orgs freely. Org-bound admins can also create
    new orgs (e.g., to set up a partner franchise).
    """
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Organization name is required")

    slug = req.name.strip().lower().replace(" ", "-")[:50]
    existing = db.query(Organization).filter(Organization.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Organization '{req.name}' already exists")

    # Validate team if provided
    team = None
    if req.team_id:
        team = db.get(Team, req.team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

    org = Organization(name=req.name.strip(), slug=slug, team_id=req.team_id)
    db.add(org)
    db.commit()
    db.refresh(org)

    return _org_dict(org)


@router.patch("/users/{user_id}/org")
def move_user_to_org(
    user_id: int,
    req: MoveUserOrgRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Move a user to a different organization (admin only).

    Super-admins (no org) can move any user to any org.
    Org-bound admins can only move users OUT of their own org
    or move unaffiliated users INTO their org.
    Passing organization_id=null removes the user from their org.
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot move yourself between organizations")

    # Permission checks for org-bound admins
    if admin.organization_id:
        # Can move users from own org, or adopt unaffiliated users
        if target.organization_id and target.organization_id != admin.organization_id:
            raise HTTPException(status_code=403, detail="Cannot move users from other organizations")
        if req.organization_id and req.organization_id != admin.organization_id:
            raise HTTPException(status_code=403, detail="Can only move users into your own organization")

    # Validate target org exists (if not removing from org)
    if req.organization_id is not None:
        dest_org = db.get(Organization, req.organization_id)
        if not dest_org:
            raise HTTPException(status_code=404, detail="Destination organization not found")

    target.organization_id = req.organization_id
    db.commit()
    db.refresh(target)

    return _user_dict(target)

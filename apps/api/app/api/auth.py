"""Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_db
from app.services.auth import register_user, authenticate_user, decode_token
from app.models.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    organization: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user, token = register_user(db, req.email, req.password, req.name, req.organization)
        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "organization_id": user.organization_id,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, token = authenticate_user(db, req.email, req.password)
        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "organization_id": user.organization_id,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
def get_me(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        user = db.get(User, int(payload["sub"]))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "organization_id": user.organization_id,
        }
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

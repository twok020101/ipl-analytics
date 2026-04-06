"""JWT authentication service."""
import jwt
from datetime import datetime, timedelta, timezone
import bcrypt
from sqlalchemy.orm import Session
from app.models.models import User, Organization, UserRole
from app.config import settings

SECRET_KEY = settings.JWT_SECRET or "ipl-analytics-secret-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int, email: str, org_id: int = None, role: str = "analyst") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "org_id": org_id,
        "role": role.value if hasattr(role, 'value') else role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def register_user(db: Session, email: str, password: str, name: str, org_name: str = None) -> tuple:
    """Register a new user. Returns (user, token) or raises ValueError."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ValueError("Email already registered")

    org = None
    if org_name:
        # Create org with slug from name
        slug = org_name.lower().replace(" ", "-")[:50]
        org = db.query(Organization).filter(Organization.slug == slug).first()
        if not org:
            org = Organization(name=org_name, slug=slug)
            db.add(org)
            db.flush()

    user = User(
        email=email,
        hashed_password=hash_password(password),
        name=name,
        role=UserRole.admin if org and not db.query(User).filter(User.organization_id == org.id).first() else UserRole.analyst,
        organization_id=org.id if org else None,
    )
    db.add(user)
    db.commit()

    token = create_access_token(user.id, user.email, user.organization_id, user.role)
    return user, token


def authenticate_user(db: Session, email: str, password: str) -> tuple:
    """Authenticate user. Returns (user, token) or raises ValueError."""
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise ValueError("Invalid email or password")
    if not user.is_active:
        raise ValueError("Account is disabled")

    token = create_access_token(user.id, user.email, user.organization_id, user.role)
    return user, token

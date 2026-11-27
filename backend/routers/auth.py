from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordRequestForm
import bcrypt
from datetime import datetime, timedelta
from jose import jwt
from pydantic import BaseModel, EmailStr
import os
import uuid
import logging
from google.oauth2 import id_token
from google.auth.transport import requests

from backend.models.user import User
from backend.schemas.user import UserCreate, UserResponse, UserUpdate
from backend.schemas.auth import Token, GoogleAuthRequest
from backend.dependencies import get_db, get_current_user, SECRET_KEY, ALGORITHM
from backend.utils.token import generate_reset_token, hash_token, verify_token_expiry
from backend.services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter()
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

class LoginJSON(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.get("/check-email")
async def check_email(email: str, db: AsyncSession = Depends(get_db)):
    """Check if an email address is already registered."""
    if not email or not email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    from sqlalchemy import func
    result = await db.execute(select(User).where(func.lower(User.email) == email.strip().lower()))
    user = result.scalars().first()
    return {"exists": user is not None, "email": email.strip()}

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = hash_password(user.password)

    role = "admin"
    parent_user_id = None
    team_to_join = None
    allowed_brands = None

    if user.invite_token and user.invite_token.strip():
        from backend.models.team import PendingInvitation
        import json
        hashed = hash_token(user.invite_token.strip())
        inv_res = await db.execute(
            select(PendingInvitation).where(
                PendingInvitation.invite_token == hashed,
                PendingInvitation.status == "pending"
            )
        )
        invite = inv_res.scalars().first()
        if invite and (not invite.expires_at or datetime.utcnow() <= invite.expires_at):
            role = "member"
            parent_user_id = invite.invited_by_user_id
            team_to_join = invite.team_id
            meta = json.loads(invite.metadata_json) if invite.metadata_json else {}
            allowed_brands = meta.get("allowed_brands")
            allowed_projects = meta.get("allowed_projects")
            invite.status = "accepted"

    db_user = User(
        email=user.email,
        password_hash=hashed_password,
        full_name=user.full_name,
        role=role,
        parent_user_id=parent_user_id,
    )
    db.add(db_user)
    await db.flush()

    if team_to_join:
        from backend.models.team import TeamMember
        db.add(
            TeamMember(
                id=str(uuid.uuid4()),
                team_id=team_to_join,
                user_id=db_user.id,
                role=role,
                allowed_brands=allowed_brands,
                allowed_projects=allowed_projects if 'allowed_projects' in locals() else None,
                joined_at=datetime.utcnow(),
            )
        )

    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.post("/login", response_model=Token)
async def login(login_data: LoginJSON, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalars().first()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/google", response_model=Token)
async def google_auth(request: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        idinfo = id_token.verify_oauth2_token(
            request.token, requests.Request(), GOOGLE_CLIENT_ID, clock_skew_in_seconds=10
        )
        email = idinfo.get('email')
        name = idinfo.get('name')
        picture = idinfo.get('picture')
        
        if not email:
            raise HTTPException(status_code=400, detail="Google authentication failed: No email provided.")

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            # Create a new user account if they don't exist
            hashed_password = hash_password(str(uuid.uuid4())) # Random placeholder password
            user = User(
                email=email,
                password_hash=hashed_password,
                full_name=name,
                avatar_url=picture
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            updated = False
            if name and not user.full_name:
                user.full_name = name
                updated = True
            if picture and (not user.avatar_url or user.avatar_url != picture):
                user.avatar_url = picture
                updated = True
            if updated:
                await db.commit()
                await db.refresh(user)

        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": access_token, "token_type": "bearer"}

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Google token: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Google auth error: {e}")

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if user_update.email and user_update.email != current_user.email:
        existing = await db.execute(select(User).where(User.email == user_update.email))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="Email is already in use")
        current_user.email = user_update.email

    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name.strip() or None

    await db.commit()
    await db.refresh(current_user)
    return current_user


# ── Password Reset Endpoints ──────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a secure password reset token and dispatches a reset email.
    Returns generic success even if user not found to prevent account enumeration.
    """
    normalized_email = body.email.strip().lower() if body.email else ""
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Email is required")

    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalars().first()

    if not user:
        # User enumeration defense: do not reveal whether user exists
        return {
            "status": "success",
            "message": "If this email is registered, a password reset link has been sent."
        }

    # Invalidate any existing reset token and generate a fresh one
    raw_token = generate_reset_token()
    user.reset_token = hash_token(raw_token)
    user.reset_token_created_at = datetime.utcnow()
    await db.commit()

    # Determine frontend URL for link generation
    frontend_url = None
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        frontend_url = origin.split("/auth")[0].rstrip("/")

    try:
        sent = send_password_reset_email(
            to_email=user.email,
            reset_token=raw_token,
            user_name=user.full_name,
            frontend_url=frontend_url,
        )
        if not sent:
            logger.warning(f"[auth.forgot_password] Email delivery returned False for {user.email}")
    except Exception as e:
        logger.error(f"[auth.forgot_password] Failed to dispatch reset email to {user.email}: {e}")

    return {
        "status": "success",
        "message": "If this email is registered, a password reset link has been sent."
    }


@router.get("/verify-reset-token")
async def verify_reset_token(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Checks if a password reset token is valid and unexpired before rendering the form.
    """
    if not token or not token.strip():
        raise HTTPException(status_code=400, detail="Token is required")

    hashed = hash_token(token)
    result = await db.execute(select(User).where(User.reset_token == hashed))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or already used reset link.")

    if not verify_token_expiry(user.reset_token_created_at, hours=1):
        raise HTTPException(status_code=400, detail="This reset link has expired. Please request a new one.")

    return {
        "valid": True,
        "email": user.email
    }


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Consumes a valid reset token and updates the user's password.
    """
    if not body.token or not body.token.strip():
        raise HTTPException(status_code=400, detail="Reset token is required")

    if not body.new_password or len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

    hashed = hash_token(body.token)
    result = await db.execute(select(User).where(User.reset_token == hashed))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link. Please request a new one.")

    if not verify_token_expiry(user.reset_token_created_at, hours=1):
        raise HTTPException(status_code=400, detail="This reset link has expired. Please request a new one.")

    # Update password and invalidate token
    user.password_hash = hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_created_at = None
    await db.commit()

    return {
        "status": "success",
        "message": "Password reset successful! You can now sign in with your new password."
    }

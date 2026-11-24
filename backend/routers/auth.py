from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordRequestForm
import bcrypt
from datetime import datetime, timedelta
from jose import jwt
from pydantic import BaseModel
import os
import uuid
from google.oauth2 import id_token
from google.auth.transport import requests

from backend.models.user import User
from backend.schemas.user import UserCreate, UserResponse, UserUpdate
from backend.schemas.auth import Token, GoogleAuthRequest
from backend.dependencies import get_db, get_current_user, SECRET_KEY, ALGORITHM

router = APIRouter()
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

class LoginJSON(BaseModel):
    email: str
    password: str

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = hash_password(user.password)
    db_user = User(
        email=user.email,
        password_hash=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
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

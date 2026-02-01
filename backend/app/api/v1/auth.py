"""
Authentication endpoints
Handles user login and JWT token generation
"""
# -*- coding: utf-8 -*-
import uuid
from datetime import timedelta
import sys

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import APIRouter, Depends, HTTPException, status
from structlog import get_logger

from app.core.config import settings
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.schemas import Token, LoginRequest, User, UserRole
from app.core.database import AsyncSessionLocal, UserModel
from sqlalchemy import select

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/token", response_model=Token)
async def login(login_request: LoginRequest):
    """
    Login endpoint - Returns JWT access token
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserModel).where(UserModel.username == login_request.username))
        user_model = result.scalar_one_or_none()
    
    if not user_model:
        logger.warning("Login attempt with unknown username", username=login_request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # [FIX] Use verify_password
    if not verify_password(login_request.password, user_model.hashed_password):
        logger.warning(f"Login failed for {login_request.username}: Password mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 일치하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user_model.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    # Create access token
    access_token_expires = timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    access_token = create_access_token(
        data={
            "sub": user_model.id,
            "tenant_id": user_model.tenant_id,
            "role": user_model.role
        },
        expires_delta=access_token_expires
    )
    
    logger.info(
        "User logged in successfully",
        user_id=user_model.id,
        username=login_request.username,
        role=user_model.role
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600
    )


@router.post("/register")
async def register(username: str, password: str, tenant_id: str = "tenant_hyungnim"):
    """
    Register a new user (development only)
    """
    async with AsyncSessionLocal() as session:
        # Check existing
        result = await session.execute(select(UserModel).where(UserModel.username == username))
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        user_id = f"user_{username}_{uuid.uuid4().hex[:8]}"
        role = UserRole.SUPER_ADMIN if username == "admin" else UserRole.STANDARD_USER
        
        new_user = UserModel(
            id=user_id,
            username=username,
            hashed_password=get_password_hash(password),
            tenant_id=tenant_id,
            role=role.value,
            is_active=1
        )
        session.add(new_user)
        await session.commit()
    
    logger.info("New user registered", username=username, user_id=user_id)
    
    return {"message": "User registered successfully", "user_id": user_id}

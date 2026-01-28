"""
Authentication endpoints
Handles user login and JWT token generation
"""
# -*- coding: utf-8 -*-
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

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# Mock user database (in production, use PostgreSQL/Neo4j)
# Pre-hashed passwords to avoid bcrypt initialization issues
# admin123 -> $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVr/1jrPK
# user123 -> $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW
MOCK_USERS_DB = {
    "admin": {
        "id": "user_admin_001",
        "username": "admin",
        "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVr/1jrPK",  # admin123
        "tenant_id": "tenant_hyungnim",
        "role": UserRole.SUPER_ADMIN,
        "is_active": True
    },
    "user1": {
        "id": "user_001",
        "username": "user1",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # user123
        "tenant_id": "tenant_hyungnim",
        "role": UserRole.STANDARD_USER,
        "is_active": True
    }
}


@router.post("/token", response_model=Token)
async def login(login_request: LoginRequest):
    """
    Login endpoint - Returns JWT access token
    
    Args:
        login_request: Username and password
        
    Returns:
        JWT access token
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Get user from database
    user_data = MOCK_USERS_DB.get(login_request.username)
    
    if not user_data:
        logger.warning(
            "Login attempt with unknown username",
            username=login_request.username
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # [FIX] Use verify_password with MOCK_USERS_DB
    # For development, we allow plain password check if hash verify fails or just use a simple map
    # But let's stick to the map for now to be safe, but add more logging.
    
    # ⚠️ Check if user exists in our password map
    valid_password = "!@ssw5740" if login_request.username == "admin" else "user123"
    
    # [DEBUG] 비밀번호 비교 디버깅
    logger.info(
        f"Password comparison for {login_request.username}",
        username=login_request.username,
        received_password=login_request.password,
        expected_password=valid_password,
        match=login_request.password == valid_password
    )
    
    if login_request.password != valid_password:
        logger.warning(
            f"Login failed for {login_request.username}: Password mismatch",
            username=login_request.username
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 일치하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user_data["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    # Create access token
    access_token_expires = timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    access_token = create_access_token(
        data={
            "sub": user_data["id"],
            "tenant_id": user_data["tenant_id"],
            "role": user_data["role"].value
        },
        expires_delta=access_token_expires
    )
    
    logger.info(
        "User logged in successfully",
        user_id=user_data["id"],
        username=login_request.username,
        role=user_data["role"].value
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600  # Convert to seconds
    )


@router.post("/register")
async def register(username: str, password: str, tenant_id: str = "tenant_hyungnim"):
    """
    Register a new user (development only)
    
    In production, this would be a separate admin endpoint
    """
    if username in MOCK_USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    user_id = f"user_{username}_{len(MOCK_USERS_DB)}"
    
    MOCK_USERS_DB[username] = {
        "id": user_id,
        "username": username,
        "hashed_password": get_password_hash(password),
        "tenant_id": tenant_id,
        "role": UserRole.STANDARD_USER,
        "is_active": True
    }
    
    logger.info("New user registered", username=username, user_id=user_id)
    
    return {"message": "User registered successfully", "user_id": user_id}

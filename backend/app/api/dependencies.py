"""
Dependencies for FastAPI endpoints
Provides reusable dependency injection functions
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token, validate_worker_token
from app.models.schemas import User, UserRole, TokenData


# Security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Dependency to get current authenticated user from JWT token
    
    Args:
        credentials: HTTP Bearer token
        
    Returns:
        Current user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user data
    user_id: str = payload.get("sub")
    tenant_id: str = payload.get("tenant_id")
    role_str: str = payload.get("role")
    
    if user_id is None or tenant_id is None or role_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        role = UserRole(role_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role in token",
        )
    
    # Fetch user from mock DB to get full details (quota, allowed_domains)
    from app.api.v1.auth import MOCK_USERS_DB
    
    # Try to find user by ID (which is stored as 'id' in MOCK_USERS_DB values)
    # Note: MOCK_USERS_DB keys are usernames, values are dicts
    user_data = None
    for u in MOCK_USERS_DB.values():
        if u["id"] == user_id:
            user_data = u
            break
            
    if not user_data:
        # Fallback if not found in DB (shouldn't happen if token is valid)
        # Construct minimal user object
        user = User(
            id=user_id,
            username=user_id,
            tenant_id=tenant_id,
            role=role,
            is_active=True
        )
    else:
        # Create User object from DB data
        user = User(**user_data)
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current active user
    
    Args:
        current_user: Current user from token
        
    Returns:
        Active user
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_super_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency to require super admin role
    
    Args:
        current_user: Current active user
        
    Returns:
        Super admin user
        
    Raises:
        HTTPException: If user is not super admin
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user


async def verify_worker_credentials(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Dependency to verify worker token
    
    Args:
        credentials: HTTP Bearer token
        
    Returns:
        Worker token
        
    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    
    if not validate_worker_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token

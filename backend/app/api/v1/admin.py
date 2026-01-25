from typing import List, Optional
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status
import sys

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from app.core.security import get_password_hash
from app.models.schemas import User, UserInDB, UserRole, UserQuota, Domain
from app.api.dependencies import get_current_user

router = APIRouter()

# Mock database for demonstration (In production, use real DB)
# This should be replaced with actual DB calls
from app.api.v1.auth import MOCK_USERS_DB

# Mock database for domains (In production, use real DB)
MOCK_DOMAINS_DB = {}

def check_super_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

@router.get("/users", response_model=List[User])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(check_super_admin)
):
    """List all users (Super Admin only)"""
    # In a real app, query the DB
    # For now, return a mock list or empty
    return list(MOCK_USERS_DB.values())[skip : skip + limit]

@router.patch("/users/{user_id}/quota", response_model=User)
async def update_user_quota(
    user_id: str,
    quota: UserQuota,
    current_user: User = Depends(check_super_admin)
):
    """Update a user's quota limits"""
    if user_id not in MOCK_USERS_DB:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_dict = MOCK_USERS_DB[user_id]
    # quota is a Pydantic model, need to convert to dict or store as is?
    # User model expects quota as UserQuota model.
    # But MOCK_USERS_DB stores dicts.
    # Let's store it as a dict in the DB mock.
    user_dict["quota"] = quota.dict()
    
    return User(**user_dict)

@router.post("/domains", response_model=Domain)
async def create_domain(
    domain: Domain,
    current_user: User = Depends(check_super_admin)
):
    """Register a new domain (project)"""
    if domain.id in MOCK_DOMAINS_DB:
        raise HTTPException(status_code=400, detail="Domain ID already exists")
    
    MOCK_DOMAINS_DB[domain.id] = domain
    return domain

@router.post("/users/{user_id}/domains", response_model=User)
async def grant_domain_access(
    user_id: str,
    domain_id: str,
    current_user: User = Depends(check_super_admin)
):
    """Grant domain access to a user"""
    # Find user by ID
    target_username = None
    user_dict = None
    for username, u in MOCK_USERS_DB.items():
        if u["id"] == user_id:
            target_username = username
            user_dict = u
            break
            
    if not user_dict:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Initialize allowed_domains if not present
    if "allowed_domains" not in user_dict:
        user_dict["allowed_domains"] = []
        
    if domain_id not in user_dict["allowed_domains"]:
        user_dict["allowed_domains"].append(domain_id)
        # MOCK_USERS_DB is mutable, so this update persists in memory
    
    return User(**user_dict)

@router.delete("/users/{user_id}/domains/{domain_id}", response_model=User)
async def revoke_domain_access(
    user_id: str,
    domain_id: str,
    current_user: User = Depends(check_super_admin)
):
    """Revoke domain access from a user"""
    if user_id not in MOCK_USERS_DB:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_dict = MOCK_USERS_DB[user_id]
    
    if "allowed_domains" in user_dict and domain_id in user_dict["allowed_domains"]:
        user_dict["allowed_domains"].remove(domain_id)
        
    return User(**user_dict)

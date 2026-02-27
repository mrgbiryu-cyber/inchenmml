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
from app.models.schemas import (
    User,
    UserInDB,
    UserRole,
    UserQuota,
    Domain,
    RuleSet,
    RuleSetPreviewRequest,
    RuleSetCloneRequest,
)
from app.api.dependencies import get_current_user
from app.core.database import AsyncSessionLocal, UserModel
from app.models.company import CompanyProfile
from app.services.rules import RulesEngine, ruleset_repository
from sqlalchemy import select

router = APIRouter()

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
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserModel).offset(skip).limit(limit))
        users = result.scalars().all()
        return [
            User(
                id=u.id,
                username=u.username,
                tenant_id=u.tenant_id,
                role=UserRole(u.role),
                is_active=bool(u.is_active)
            ) for u in users
        ]

@router.patch("/users/{user_id}/quota", response_model=User)
async def update_user_quota(
    user_id: str,
    quota: UserQuota,
    current_user: User = Depends(check_super_admin)
):
    """Update a user's quota limits"""
    # TODO: Implement quota in RDB
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Currently UserModel doesn't support quota
        return User(
            id=user.id,
            username=user.username,
            tenant_id=user.tenant_id,
            role=UserRole(user.role),
            is_active=bool(user.is_active)
        )

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
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # TODO: Implement allowed_domains in RDB or UserProjectModel
        return User(
            id=user.id,
            username=user.username,
            tenant_id=user.tenant_id,
            role=UserRole(user.role),
            is_active=bool(user.is_active)
        )

@router.delete("/users/{user_id}/domains/{domain_id}", response_model=User)
async def revoke_domain_access(
    user_id: str,
    domain_id: str,
    current_user: User = Depends(check_super_admin)
):
    """Revoke domain access from a user"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # TODO: Implement allowed_domains in RDB or UserProjectModel
        return User(
            id=user.id,
            username=user.username,
            tenant_id=user.tenant_id,
            role=UserRole(user.role),
            is_active=bool(user.is_active)
        )


@router.get("/rulesets", response_model=List[RuleSet])
async def list_rulesets(
    ruleset_id: str = "company-growth-default",
    current_user: User = Depends(check_super_admin)
):
    """List all ruleset versions."""
    return ruleset_repository.list_rulesets(ruleset_id)


@router.post("/rulesets", response_model=RuleSet, status_code=status.HTTP_201_CREATED)
async def create_ruleset(
    ruleset: RuleSet,
    current_user: User = Depends(check_super_admin)
):
    """Create a new ruleset version."""
    ruleset.author = current_user.username
    try:
        return ruleset_repository.create(ruleset)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/rulesets/{ruleset_id}/{version}", response_model=RuleSet)
async def update_ruleset(
    ruleset_id: str,
    version: str,
    payload: RuleSet,
    current_user: User = Depends(check_super_admin)
):
    """Update an existing ruleset version."""
    if payload.ruleset_id != ruleset_id or payload.version != version:
        raise HTTPException(status_code=400, detail="Path and payload version mismatch")
    payload.author = current_user.username
    try:
        return ruleset_repository.save(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/rulesets/{ruleset_id}/{version}/activate", response_model=RuleSet)
async def activate_ruleset(
    ruleset_id: str,
    version: str,
    current_user: User = Depends(check_super_admin)
):
    """Activate a ruleset version and archive currently active version."""
    try:
        return ruleset_repository.activate(ruleset_id, version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/rulesets/{ruleset_id}/{version}/clone", response_model=RuleSet)
async def clone_ruleset(
    ruleset_id: str,
    version: str,
    body: RuleSetCloneRequest,
    current_user: User = Depends(check_super_admin)
):
    """Clone a ruleset into a new draft version."""
    try:
        return ruleset_repository.clone(
            ruleset_id=ruleset_id,
            source_version=version,
            new_version=body.version,
            author=current_user.username,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/rulesets/{ruleset_id}/active", response_model=RuleSet)
async def get_active_ruleset(
    ruleset_id: str,
    current_user: User = Depends(check_super_admin)
):
    """Get active ruleset."""
    try:
        return ruleset_repository.get_active(ruleset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/rulesets/{ruleset_id}/{version}/preview")
async def preview_ruleset(
    ruleset_id: str,
    version: str,
    body: RuleSetPreviewRequest,
    current_user: User = Depends(check_super_admin)
):
    """Preview ruleset decision against input profile."""
    try:
        ruleset = ruleset_repository.get(ruleset_id, version)
        engine = RulesEngine(ruleset)
        profile = CompanyProfile(**body.profile.dict())
        return engine.classify_profile(profile)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

"""
Security utilities for BUJA Core Platform
Implements JWT authentication, password hashing, and Ed25519 job signing
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import base64

from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================
# Password Hashing
# ============================================

def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================
# JWT Token Management
# ============================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Payload data to encode (should include 'sub', 'tenant_id', 'role')
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token
    
    Args:
        token: JWT token to decode
        
    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


# ============================================
# Ed25519 Job Signing (CRITICAL SECURITY)
# ============================================

class SecurityError(Exception):
    """Raised when security validation fails"""
    pass


def sign_job_payload(job_data: dict) -> str:
    """
    Sign a job payload with Backend's Ed25519 private key
    
    This is the ONLY way to create valid jobs. Jobs without valid signatures
    will be rejected by Local Workers.
    
    Args:
        job_data: Job dictionary (without 'signature' field)
        
    Returns:
        Base64-encoded signature string (format: "base64:...")
        
    Raises:
        SecurityError: If private key is invalid or signing fails
        
    Implementation follows JOB_AND_SECURITY.md Section 3.3
    """
    try:
        # 1. Load private key from environment
        private_key_pem = settings.JOB_SIGNING_PRIVATE_KEY
        
        if not private_key_pem:
            raise SecurityError("JOB_SIGNING_PRIVATE_KEY not configured")
            
        # Handle literal \n characters from .env
        private_key_pem = private_key_pem.replace('\\n', '\n')
        
        # Handle both raw PEM and environment variable formats
        if not private_key_pem.startswith("-----BEGIN"):
            # If stored as base64 or single line, reconstruct PEM
            raise SecurityError(
                "JOB_SIGNING_PRIVATE_KEY must be in PEM format. "
                "Generate with: python -c 'from cryptography.hazmat.primitives.asymmetric import ed25519; ...'"
            )
        
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None
        )
        
        # Verify it's an Ed25519 key
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise SecurityError("Private key is not Ed25519 format")
        
        # 2. Create canonical JSON (sorted keys, no whitespace)
        # This ensures the same job always produces the same signature
        canonical_json = json.dumps(job_data, sort_keys=True, separators=(',', ':'))
        message = canonical_json.encode('utf-8')
        
        # 3. Sign the message
        signature_bytes = private_key.sign(message)
        
        # 4. Encode as base64
        signature_b64 = base64.b64encode(signature_bytes).decode('ascii')
        
        return f"base64:{signature_b64}"
        
    except Exception as e:
        if isinstance(e, SecurityError):
            raise
        raise SecurityError(f"Job signing failed: {str(e)}")


def verify_job_signature(job_dict: dict, public_key_pem: str) -> bool:
    """
    Verify job signature with Backend's public key
    
    This function is primarily for testing. In production, only Local Workers
    verify signatures.
    
    Args:
        job_dict: Complete job including 'signature' field
        public_key_pem: Ed25519 public key in PEM format
        
    Returns:
        True if valid
        
    Raises:
        SecurityError: If signature is invalid
        
    Implementation follows JOB_AND_SECURITY.md Section 3.3
    """
    try:
        # 1. Extract signature
        job_copy = job_dict.copy()
        signature_field = job_copy.pop('signature', None)
        
        if not signature_field:
            raise SecurityError("Job missing signature field")
        
        if not signature_field.startswith('base64:'):
            raise SecurityError("Invalid signature format (must start with 'base64:')")
        
        signature_b64 = signature_field.replace('base64:', '')
        signature_bytes = base64.b64decode(signature_b64)
        
        # 2. Load public key
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        
        if not isinstance(public_key, ed25519.Ed25519PublicKey):
            raise SecurityError("Public key is not Ed25519 format")
        
        # 3. Recreate canonical message
        canonical_json = json.dumps(job_copy, sort_keys=True, separators=(',', ':'))
        message = canonical_json.encode('utf-8')
        
        # 4. Verify signature
        try:
            public_key.verify(signature_bytes, message)
            return True
        except InvalidSignature:
            raise SecurityError(
                f"Job signature verification failed for job_id={job_copy.get('job_id')}"
            )
            
    except Exception as e:
        if isinstance(e, SecurityError):
            raise
        raise SecurityError(f"Signature verification failed: {str(e)}")


# ============================================
# Worker Token Validation
# ============================================

def validate_worker_token(token: str) -> bool:
    """
    Validate a worker token
    
    In production, this should check against a database of issued tokens.
    For now, we just verify the format.
    
    Args:
        token: Worker token (format: sk_worker_...)
        
    Returns:
        True if valid format
    """
    if not token:
        return False
    
    # Basic format validation
    if not token.startswith("sk_worker_"):
        return False
    
    # In production: Check against Redis/DB
    # await redis.exists(f"worker_token:{token}")
    
    return True

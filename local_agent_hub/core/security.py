"""
Security utilities for Local Worker
Implements Ed25519 signature verification and path validation
"""
from pathlib import Path
from typing import List
import json
import base64

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class SecurityError(Exception):
    """Raised when security validation fails"""
    pass


# ============================================
# Ed25519 Signature Verification
# ============================================

def verify_job_signature(job_dict: dict, public_key_pem: str) -> bool:
    """
    Verify job signature with Backend's Ed25519 public key
    
    This is the CRITICAL security gate. Jobs with invalid signatures
    are rejected to prevent tampering.
    
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
        
        # 3. Recreate canonical message (MUST match backend's canonical JSON)
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
# Path Validation (6-Layer Security)
# ============================================

def validate_path(
    file_path: str,
    repo_root: str,
    allowed_prefixes: List[str],
    forbidden_patterns: List[str] = None
) -> Path:
    """
    Comprehensive path validation with multiple security layers
    
    Implementation follows INTEGRATIONS_AND_OPS.md Section 6.1 EXACTLY
    
    Args:
        file_path: Relative or absolute path from Job
        repo_root: Job's project root (absolute)
        allowed_prefixes: Whitelist (e.g., ["src/", "tests/"])
        forbidden_patterns: Blacklist (e.g., ["../", "~"])
        
    Returns:
        Validated absolute Path object
        
    Raises:
        SecurityError: If any validation fails
    """
    if forbidden_patterns is None:
        forbidden_patterns = ["../", "~/", "~", "/etc/", "/root/", "/sys/", "/proc/"]
    
    # Layer 1: Convert to absolute and resolve symlinks
    try:
        if Path(file_path).is_absolute():
            # Absolute paths not allowed in relative context
            raise SecurityError(
                f"Absolute path not allowed: {file_path}"
            )
        
        abs_path = (Path(repo_root) / file_path).resolve()
        abs_root = Path(repo_root).resolve()
    except (ValueError, OSError) as e:
        raise SecurityError(f"Invalid path format: {file_path} ({e})")
    
    # Layer 2: Ensure path is inside repo_root
    try:
        abs_path.relative_to(abs_root)
    except ValueError:
        raise SecurityError(
            f"Path traversal detected: {file_path} "
            f"escapes {repo_root}"
        )
    
    # Layer 3: Check forbidden patterns
    path_str = str(abs_path)
    file_path_str = str(file_path)
    
    for pattern in forbidden_patterns:
        if pattern in file_path_str or pattern in path_str:
            raise SecurityError(
                f"Forbidden pattern '{pattern}' in path: {file_path}"
            )
    
    # Layer 4: System directory blacklist (absolute protection)
    SYSTEM_DIRS = [
        "/etc/", "/root/", "/sys/", "/proc/", "/boot/",
        "/dev/", "/var/", "/usr/bin/", "/usr/sbin/",
        "/home/.ssh/", "/home/.aws/", "/home/.kube/",
        # Windows system directories
        "C:\\Windows\\", "C:\\Program Files\\", "C:\\ProgramData\\",
        "C:\\Users\\All Users\\", "C:\\Users\\Default\\"
    ]
    
    for sys_dir in SYSTEM_DIRS:
        if path_str.startswith(sys_dir) or sys_dir in path_str:
            raise SecurityError(
                f"Access to system directory forbidden: {sys_dir}"
            )
    
    # Layer 5: Whitelist prefix validation
    relative_path = abs_path.relative_to(abs_root)
    relative_str = str(relative_path).replace('\\', '/')  # Normalize for Windows
    
    # Special case: root-level files (e.g., README.md)
    if "/" not in relative_str and len(allowed_prefixes) > 0:
        # Root file access only if explicitly allowed via empty prefix
        if "" not in allowed_prefixes:
            raise SecurityError(
                f"Root-level file access not allowed: {file_path}. "
                f"Allowed prefixes: {allowed_prefixes}"
            )
    else:
        # Check if path starts with any allowed prefix
        is_allowed = any(
            relative_str.startswith(prefix) 
            for prefix in allowed_prefixes
        )
        
        if not is_allowed:
            raise SecurityError(
                f"Path not in allowed directories: {file_path}\n"
                f"Allowed prefixes: {allowed_prefixes}\n"
                f"Attempted: {relative_str}"
            )
    
    # Layer 6: Symlink destination validation (if path is symlink)
    if abs_path.is_symlink():
        real_path = abs_path.resolve()
        # Recursively validate the symlink target
        try:
            real_path.relative_to(abs_root)
        except ValueError:
            raise SecurityError(
                f"Symlink points outside repo_root: {file_path} -> {real_path}"
            )
    
    return abs_path


def validate_job_paths(job: dict) -> None:
    """
    Validate all file paths in a Job before execution
    
    Args:
        job: Job dictionary
        
    Raises:
        SecurityError: On first validation failure
    """
    repo_root = job.get('repo_root')
    allowed = job.get('allowed_paths', [])
    
    forbidden = [
        "../", "~/", "~", "/etc/", "/root/", "/sys/", "/proc/"
    ]
    
    # Validate repo_root itself
    if not repo_root:
        raise SecurityError("Job missing repo_root")
    
    repo_path = Path(repo_root)
    
    # On Windows, /foo is not absolute (needs drive letter). 
    # But it resolves to D:\foo which IS absolute.
    if not repo_path.is_absolute():
        resolved = repo_path.resolve()
        if resolved.is_absolute():
            repo_path = resolved
            # We don't update job['repo_root'] here as it might break signature, 
            # but we use repo_path for existence check.
        else:
            raise SecurityError(f"repo_root must be absolute: {repo_root}")
    
    if not repo_path.exists():
        raise SecurityError(f"repo_root does not exist: {repo_root} (resolved: {repo_path})")
    
    # Validate each file operation
    for file_op in job.get('file_operations', []):
        file_path = file_op.get('path')
        
        if not file_path:
            continue
        
        try:
            validated_path = validate_path(
                file_path,
                repo_root,
                allowed,
                forbidden
            )
            
            print(f"✅ Path validated: {file_path} -> {validated_path}")
            
        except SecurityError as e:
            print(f"🔒 Path validation failed: {e}")
            raise


# ============================================
# File Size Validation
# ============================================

def validate_file_size(content: str, path: str, max_size: int = 1048576) -> None:
    """
    Check file size before writing
    
    Args:
        content: File content
        path: File path (for error message)
        max_size: Maximum size in bytes (default 1 MB)
        
    Raises:
        SecurityError: If file too large
    """
    size_bytes = len(content.encode('utf-8'))
    
    if size_bytes > max_size:
        raise SecurityError(
            f"File too large: {path} ({size_bytes} bytes, max {max_size})"
        )


def validate_total_job_size(job: dict, max_size: int = 10485760) -> None:
    """
    Check total size of all files in job
    
    Args:
        job: Job dictionary
        max_size: Maximum total size in bytes (default 10 MB)
        
    Raises:
        SecurityError: If total size too large
    """
    total = 0
    
    for file_op in job.get('file_operations', []):
        content = file_op.get('content', '')
        total += len(content.encode('utf-8'))
    
    if total > max_size:
        raise SecurityError(
            f"Job total size too large: {total} bytes, max {max_size}"
        )

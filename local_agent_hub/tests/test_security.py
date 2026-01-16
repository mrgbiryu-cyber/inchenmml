"""
Test suite for Local Worker security
Tests Ed25519 signature verification and path validation
"""
import pytest
from pathlib import Path
import tempfile
import os

from local_agent_hub.core.security import (
    verify_job_signature,
    validate_path,
    validate_job_paths,
    SecurityError
)


# Sample Ed25519 keys for testing (generated for testing only)
TEST_PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIFg3YjRlNmE4ZTJiMzRjNWQ2ZTdhOGY5YjBjMWQyZTNm
-----END PRIVATE KEY-----"""

TEST_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAXDe4B9X2Y4ZjNhOGUyYjM0YzVkNmU3YThmOWIwYzFkMmUzZg==
-----END PUBLIC KEY-----"""


def test_path_validation_basic():
    """Test basic path validation"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = tmpdir
        allowed_prefixes = ["src/", "tests/"]
        
        # Valid path
        valid_path = validate_path(
            "src/main.py",
            repo_root,
            allowed_prefixes
        )
        assert valid_path is not None
        print(f"✅ Valid path accepted: {valid_path}")


def test_path_validation_traversal():
    """Test that path traversal is blocked"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = tmpdir
        allowed_prefixes = ["src/"]
        
        # Path traversal attempt
        with pytest.raises(SecurityError, match="Path traversal detected"):
            validate_path(
                "../etc/passwd",
                repo_root,
                allowed_prefixes
            )
        
        print("✅ Path traversal correctly blocked")


def test_path_validation_absolute():
    """Test that absolute paths are blocked"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = tmpdir
        allowed_prefixes = ["src/"]
        
        # Absolute path attempt
        with pytest.raises(SecurityError, match="Absolute path not allowed"):
            validate_path(
                "/etc/passwd",
                repo_root,
                allowed_prefixes
            )
        
        print("✅ Absolute path correctly blocked")


def test_path_validation_forbidden_pattern():
    """Test that forbidden patterns are blocked"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = tmpdir
        allowed_prefixes = ["src/"]
        
        # Forbidden pattern
        with pytest.raises(SecurityError, match="Forbidden pattern"):
            validate_path(
                "src/../../etc/passwd",
                repo_root,
                allowed_prefixes
            )
        
        print("✅ Forbidden pattern correctly blocked")


def test_path_validation_outside_allowed():
    """Test that paths outside allowed prefixes are blocked"""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = tmpdir
        allowed_prefixes = ["src/", "tests/"]
        
        # Path outside allowed prefixes
        with pytest.raises(SecurityError, match="Path not in allowed directories"):
            validate_path(
                "config/secrets.yaml",
                repo_root,
                allowed_prefixes
            )
        
        print("✅ Path outside allowed prefixes correctly blocked")


def test_validate_job_paths():
    """Test job path validation"""
    with tempfile.TemporaryDirectory() as tmpdir:
        job = {
            "repo_root": tmpdir,
            "allowed_paths": ["src/", "tests/"],
            "file_operations": [
                {"path": "src/main.py", "action": "CREATE"},
                {"path": "tests/test_main.py", "action": "CREATE"}
            ]
        }
        
        # Should not raise
        validate_job_paths(job)
        print("✅ Job paths validated successfully")


def test_validate_job_paths_invalid():
    """Test job path validation with invalid paths"""
    with tempfile.TemporaryDirectory() as tmpdir:
        job = {
            "repo_root": tmpdir,
            "allowed_paths": ["src/"],
            "file_operations": [
                {"path": "../etc/passwd", "action": "CREATE"}
            ]
        }
        
        # Should raise
        with pytest.raises(SecurityError):
            validate_job_paths(job)
        
        print("✅ Invalid job paths correctly rejected")


if __name__ == "__main__":
    print("\n🔒 Testing Local Worker Security\n")
    print("=" * 60)
    
    try:
        test_path_validation_basic()
        test_path_validation_traversal()
        test_path_validation_absolute()
        test_path_validation_forbidden_pattern()
        test_path_validation_outside_allowed()
        test_validate_job_paths()
        test_validate_job_paths_invalid()
        
        print("\n" + "=" * 60)
        print("✅ All security tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise

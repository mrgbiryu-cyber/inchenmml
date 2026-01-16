"""
Test suite for Ed25519 job signing
Verifies the signature implementation matches JOB_AND_SECURITY.md specifications
"""
import pytest
from uuid import uuid4
import time

from app.core.security import sign_job_payload, verify_job_signature, SecurityError
from app.core.config import settings


def test_sign_job_payload():
    """Test that job signing produces valid base64 signature"""
    job_data = {
        "job_id": str(uuid4()),
        "tenant_id": "tenant_test",
        "user_id": "user_test",
        "execution_location": "LOCAL_MACHINE",
        "provider": "OLLAMA",
        "model": "mimo-v2-flash",
        "created_at_ts": int(time.time()),
        "status": "QUEUED",
        "timeout_sec": 600,
        "idempotency_key": "sha256:test123",
        "repo_root": "/test/path",
        "allowed_paths": ["src/"]
    }
    
    # Sign the job
    signature = sign_job_payload(job_data)
    
    # Verify format
    assert signature.startswith("base64:")
    assert len(signature) > 10
    
    print(f"✅ Job signed successfully: {signature[:30]}...")


def test_verify_job_signature():
    """Test that signature verification works correctly"""
    job_data = {
        "job_id": str(uuid4()),
        "tenant_id": "tenant_test",
        "user_id": "user_test",
        "execution_location": "CLOUD",
        "provider": "OPENROUTER",
        "model": "deepseek-chat",
        "created_at_ts": int(time.time()),
        "status": "QUEUED",
        "timeout_sec": 300,
        "idempotency_key": "sha256:test456"
    }
    
    # Sign the job
    signature = sign_job_payload(job_data)
    job_data["signature"] = signature
    
    # Verify with public key
    public_key = settings.JOB_SIGNING_PUBLIC_KEY
    
    result = verify_job_signature(job_data, public_key)
    assert result is True
    
    print("✅ Signature verification successful")


def test_tampered_job_fails_verification():
    """Test that tampered jobs fail verification"""
    job_data = {
        "job_id": str(uuid4()),
        "tenant_id": "tenant_test",
        "user_id": "user_test",
        "execution_location": "CLOUD",
        "provider": "OPENROUTER",
        "model": "deepseek-chat",
        "created_at_ts": int(time.time()),
        "status": "QUEUED",
        "timeout_sec": 300,
        "idempotency_key": "sha256:test789"
    }
    
    # Sign the job
    signature = sign_job_payload(job_data)
    job_data["signature"] = signature
    
    # Tamper with the job
    job_data["user_id"] = "attacker_user"
    
    # Verification should fail
    public_key = settings.JOB_SIGNING_PUBLIC_KEY
    
    with pytest.raises(SecurityError, match="signature verification failed"):
        verify_job_signature(job_data, public_key)
    
    print("✅ Tampered job correctly rejected")


if __name__ == "__main__":
    print("\n🔒 Testing Ed25519 Job Signing Implementation\n")
    print("=" * 60)
    
    try:
        test_sign_job_payload()
        test_verify_job_signature()
        test_tampered_job_fails_verification()
        
        print("\n" + "=" * 60)
        print("✅ All signature tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise

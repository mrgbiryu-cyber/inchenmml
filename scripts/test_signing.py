"""
Test Ed25519 signing and verification directly
"""
import sys
from pathlib import Path

# Add both backend and worker to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'local_agent_hub'))

from app.core.security import sign_job_payload
from core.security import verify_job_signature
from app.core.config import settings

print("=" * 70)
print("Ed25519 Signing Test")
print("=" * 70)
print()

# Test job data
job_data = {
    "job_id": "test-123",
    "tenant_id": "tenant_test",
    "user_id": "user_test",
    "execution_location": "LOCAL_MACHINE",
    "provider": "OLLAMA",
    "model": "test-model",
    "timeout_sec": 60,
    "repo_root": "C:/temp/test",
    "allowed_paths": [""],
    "metadata": {},
    "file_operations": [],
    "status": "QUEUED",
    "created_at_ts": 1234567890
}

print("1. Signing job with backend private key...")
try:
    signature = sign_job_payload(job_data)
    print(f"   ✅ Signature: {signature[:50]}...")
    job_data["signature"] = signature
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("2. Verifying signature with worker public key...")

# Load public key from agents.yaml
import yaml
agents_yaml_path = Path(__file__).parent.parent / 'local_agent_hub' / 'agents.yaml'
with open(agents_yaml_path) as f:
    config = yaml.safe_load(f)
    public_key = config['security']['job_signing_public_key']

try:
    verify_job_signature(job_data, public_key)
    print("   ✅ Signature verified successfully!")
    print()
    print("=" * 70)
    print("🎉 Keys are correctly matched!")
    print("=" * 70)
except Exception as e:
    print(f"   ❌ Verification failed: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("=" * 70)
    print("❌ Keys do NOT match!")
    print("=" * 70)

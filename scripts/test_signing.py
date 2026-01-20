"""
Test Ed25519 signing and verification directly
"""
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock
from dotenv import dotenv_values
import yaml

# Get project root (d:\project\myllm)
project_root = Path(__file__).parent.parent

# Add project root to path to allow 'import local_agent_hub'
sys.path.insert(0, str(project_root))

# Add backend to path to allow 'import app'
sys.path.insert(0, str(project_root / 'backend'))

# ==========================================
# 1. Load Keys Manually
# ==========================================

# Load Private Key from .env
env_path = project_root / 'backend' / '.env'
env_config = dotenv_values(env_path)
private_key_pem = env_config.get("JOB_SIGNING_PRIVATE_KEY")

if not private_key_pem:
    print("❌ Could not load JOB_SIGNING_PRIVATE_KEY from .env")
    sys.exit(1)

# Clean up the key
if private_key_pem.startswith('"') and private_key_pem.endswith('"'):
    private_key_pem = private_key_pem[1:-1]
private_key_pem = private_key_pem.replace('\\n', '\n')

# Load Public Key from agents.yaml
agents_yaml_path = project_root / 'local_agent_hub' / 'agents.yaml'
with open(agents_yaml_path) as f:
    config = yaml.safe_load(f)
    public_key_pem = config['security']['job_signing_public_key']

# ==========================================
# 2. Mock Configuration to Bypass Pydantic
# ==========================================

# Mock app.core.config module BEFORE importing app.core.security
config_mock = MagicMock()
sys.modules['app.core.config'] = config_mock

# Mock settings instance
settings_mock = MagicMock()
config_mock.settings = settings_mock
settings_mock.JOB_SIGNING_PRIVATE_KEY = private_key_pem

# ==========================================
# 3. Import Security Modules
# ==========================================

try:
    from app.core.security import sign_job_payload
    from local_agent_hub.core.security import verify_job_signature
except ImportError as e:
    print(f"❌ Import Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ==========================================
# 4. Run Test
# ==========================================

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

try:
    verify_job_signature(job_data, public_key_pem)
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

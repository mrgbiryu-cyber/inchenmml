"""
Standalone Ed25519 Key Verification Script
Copies logic from app/core/security.py to avoid dependency issues
"""
import sys
import json
import base64
from pathlib import Path
from dotenv import dotenv_values
import yaml
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

# Get project root
project_root = Path(__file__).parent.parent

# ==========================================
# 1. Load Keys
# ==========================================

print("=" * 70)
print("Loading Keys...")
print("=" * 70)

# Load Private Key from .env
env_path = project_root / 'backend' / '.env'
env_config = dotenv_values(env_path)
private_key_pem = env_config.get("JOB_SIGNING_PRIVATE_KEY")

if not private_key_pem:
    print("❌ Could not load JOB_SIGNING_PRIVATE_KEY from .env")
    sys.exit(1)

# Clean up private key
if private_key_pem.startswith('"') and private_key_pem.endswith('"'):
    private_key_pem = private_key_pem[1:-1]
private_key_pem = private_key_pem.replace('\\n', '\n')

print("✅ Private Key loaded")

# Load Public Key from agents.yaml
agents_yaml_path = project_root / 'local_agent_hub' / 'agents.yaml'
with open(agents_yaml_path, encoding='utf-8') as f:
    config = yaml.safe_load(f)
    public_key_pem = config['security']['job_signing_public_key']

print("✅ Public Key loaded")
print()

# ==========================================
# 2. Signing Logic (Copied from Backend)
# ==========================================

def sign_job_payload(job_data: dict, private_key_str: str) -> str:
    try:
        # Load private key
        private_key = serialization.load_pem_private_key(
            private_key_str.encode(),
            password=None
        )
        
        # Create canonical JSON (sorted keys, no whitespace)
        canonical_json = json.dumps(job_data, sort_keys=True, separators=(',', ':'))
        message = canonical_json.encode('utf-8')
        
        # Sign
        signature_bytes = private_key.sign(message)
        
        # Encode
        signature_b64 = base64.b64encode(signature_bytes).decode('ascii')
        
        return f"base64:{signature_b64}"
    except Exception as e:
        raise Exception(f"Signing failed: {e}")

# ==========================================
# 3. Verification Logic (Copied from Worker)
# ==========================================

def verify_job_signature(job_dict: dict, public_key_str: str) -> bool:
    try:
        # Extract signature
        job_copy = job_dict.copy()
        signature_field = job_copy.pop('signature', None)
        
        if not signature_field:
            raise Exception("No signature field")
            
        signature_b64 = signature_field.replace('base64:', '')
        signature_bytes = base64.b64decode(signature_b64)
        
        # Load public key
        public_key = serialization.load_pem_public_key(public_key_str.encode())
        
        # Recreate canonical message
        canonical_json = json.dumps(job_copy, sort_keys=True, separators=(',', ':'))
        message = canonical_json.encode('utf-8')
        
        # Verify
        public_key.verify(signature_bytes, message)
        return True
    except Exception as e:
        raise Exception(f"Verification failed: {e}")

# ==========================================
# 4. Run Test
# ==========================================

print("=" * 70)
print("Testing Key Pair Compatibility")
print("=" * 70)
print()

# Test job data
job_data = {
    "job_id": "test-123",
    "tenant_id": "tenant_test",
    "status": "QUEUED",
    "created_at_ts": 1234567890
}

print("1. Signing with Private Key...")
try:
    signature = sign_job_payload(job_data, private_key_pem)
    print(f"   ✅ Generated Signature: {signature[:50]}...")
    job_data["signature"] = signature
except Exception as e:
    print(f"   ❌ Signing Error: {e}")
    sys.exit(1)

print()
print("2. Verifying with Public Key...")
try:
    verify_job_signature(job_data, public_key_pem)
    print("   ✅ Verification Successful!")
    print()
    print("=" * 70)
    print("🎉 KEYS ARE MATCHED AND VALID")
    print("=" * 70)
except Exception as e:
    print(f"   ❌ Verification Failed: {e}")
    print()
    print("=" * 70)
    print("❌ KEYS DO NOT MATCH")
    print("=" * 70)
    print()
    print("Private Key (first 50):")
    print(private_key_pem[:50])
    print()
    print("Public Key (first 50):")
    print(public_key_pem[:50])

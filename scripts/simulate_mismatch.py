"""
Simulate Backend Signing vs Worker Verification Mismatch
Checks if UUID/Enum serialization causes signature failure
"""
import sys
import json
import base64
from uuid import uuid4, UUID
from enum import Enum
from pathlib import Path
from dotenv import dotenv_values
import yaml
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Get project root
project_root = Path(__file__).parent.parent

# Load Keys
env_path = project_root / 'backend' / '.env'
env_config = dotenv_values(env_path)
private_key_pem = env_config.get("JOB_SIGNING_PRIVATE_KEY").replace('\\n', '\n')
if private_key_pem.startswith('"'): private_key_pem = private_key_pem[1:-1]

agents_yaml_path = project_root / 'local_agent_hub' / 'agents.yaml'
with open(agents_yaml_path) as f:
    config = yaml.safe_load(f)
    public_key_pem = config['security']['job_signing_public_key']

# ==========================================
# Mock Classes
# ==========================================

class ExecutionLocation(str, Enum):
    LOCAL_MACHINE = "LOCAL_MACHINE"

class ProviderType(str, Enum):
    OLLAMA = "OLLAMA"

# ==========================================
# 1. Backend Signing (Simulating job_manager.py)
# ==========================================

def backend_sign(job_data, private_key_str):
    # job_manager.py passes the dictionary directly to sign_job_payload
    # BUT the dictionary contains UUID objects and Enums!
    
    # app/core/security.py:
    # canonical_json = json.dumps(job_data, sort_keys=True, separators=(',', ':'))
    
    # Standard json.dumps fails with UUID/Enum unless a custom encoder is used.
    # However, sign_job_payload in security.py DOES NOT use a custom encoder.
    # It just calls json.dumps().
    
    # Wait, if job_manager.py passes UUID objects, json.dumps() inside sign_job_payload SHOULD FAIL.
    # If it doesn't fail, then job_manager.py must be converting them to strings first.
    
    # Let's check what job_manager.py actually does:
    # job_data = { "job_id": str(job_id), ... "execution_location": job_request.execution_location.value }
    # Ah! It converts UUID to str and Enum to value.
    
    try:
        private_key = serialization.load_pem_private_key(private_key_str.encode(), password=None)
        canonical_json = json.dumps(job_data, sort_keys=True, separators=(',', ':'))
        print(f"Backend Canonical JSON: {canonical_json}")
        
        message = canonical_json.encode('utf-8')
        signature_bytes = private_key.sign(message)
        return f"base64:{base64.b64encode(signature_bytes).decode('ascii')}"
    except Exception as e:
        print(f"Backend Signing Error: {e}")
        raise

# ==========================================
# 2. Worker Verification (Simulating poller.py)
# ==========================================

def worker_verify(job_json_str, public_key_str):
    # Worker receives JSON string from HTTP response
    job_dict = json.loads(job_json_str)
    
    # Extract signature
    signature_field = job_dict.pop('signature')
    signature_b64 = signature_field.replace('base64:', '')
    signature_bytes = base64.b64decode(signature_b64)
    
    # Recreate canonical message
    canonical_json = json.dumps(job_dict, sort_keys=True, separators=(',', ':'))
    print(f"Worker Canonical JSON:  {canonical_json}")
    
    public_key = serialization.load_pem_public_key(public_key_str.encode())
    try:
        public_key.verify(signature_bytes, canonical_json.encode('utf-8'))
        return True
    except Exception as e:
        print(f"Worker Verification Error: {e}")
        return False

# ==========================================
# 3. Simulation
# ==========================================

print("=" * 70)
print("Simulating Data Mismatch")
print("=" * 70)

# Data as created in job_manager.py
job_id = uuid4()
job_data_backend = {
    "job_id": str(job_id),  # Converted to string
    "tenant_id": "tenant_test",
    "execution_location": "LOCAL_MACHINE", # Enum value
    "created_at_ts": 1234567890,
    "metadata": {}, # Empty dict
    "steps": [] # Empty list
}

print("1. Backend signs the job...")
signature = backend_sign(job_data_backend, private_key_pem)
job_data_backend["signature"] = signature

# Simulate HTTP/Redis Transport (Serialize -> Deserialize)
job_json_str = json.dumps(job_data_backend)
print(f"\nTransport JSON: {job_json_str}\n")

print("2. Worker verifies the job...")
result = worker_verify(job_json_str, public_key_pem)

if result:
    print("\n✅ Verification SUCCESS")
else:
    print("\n❌ Verification FAILED")

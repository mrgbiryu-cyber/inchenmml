# BUJA Local Worker - Quick Start Guide

## 🚀 Running the Local Worker

### 1. Install Dependencies

```bash
cd local_agent_hub
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Worker

Create `agents.yaml` from the example:

```bash
cp agents.yaml.example agents.yaml
```

Edit `agents.yaml` with your configuration:

```yaml
server:
  url: http://localhost:8000  # Backend URL
  worker_token: sk_worker_1234567890abcdef  # From Super Admin
  poll_interval: 5
  timeout: 30
  heartbeat_interval: 30

capabilities:
  - provider: OLLAMA
    model: mimo-v2-flash
    endpoint: http://localhost:11434
    timeout: 120
    max_concurrent: 3

security:
  # Ed25519 public key (copy from Backend's JOB_SIGNING_PUBLIC_KEY)
  job_signing_public_key: |
    -----BEGIN PUBLIC KEY-----
    MCowBQYDK2VwAyEA...
    -----END PUBLIC KEY-----
  
  allowed_path_prefixes:
    - "src/"
    - "tests/"
    - "docs/"
  
  forbidden_absolute_paths:
    - "/etc/"
    - "/root/"
    - "/sys/"
    - "/proc/"
    - "~/.ssh/"
    - "~/.aws/"
```

### 3. Run the Worker

```bash
cd local_agent_hub
python main.py
```

Expected output:
```
🚀 BUJA Local Worker starting
worker_id='worker_001' server_url='http://localhost:8000'
Starting job polling loop...
```

---

## 🧪 Testing the Worker

### 1. Test Path Validation

```bash
cd local_agent_hub
pytest tests/test_security.py -v
```

Expected output:
```
🔒 Testing Local Worker Security
============================================================
✅ Valid path accepted
✅ Path traversal correctly blocked
✅ Absolute path correctly blocked
✅ Forbidden pattern correctly blocked
✅ Path outside allowed prefixes correctly blocked
✅ Job paths validated successfully
✅ Invalid job paths correctly rejected
============================================================
✅ All security tests passed!
```

### 2. Test End-to-End Flow

**Terminal 1 - Start Backend:**
```bash
cd backend
python -m app.main
```

**Terminal 2 - Start Worker:**
```bash
cd local_agent_hub
python main.py
```

**Terminal 3 - Create Job:**
```bash
# Login as admin
export TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | jq -r '.access_token')

# Create a job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "execution_location": "LOCAL_MACHINE",
    "provider": "OLLAMA",
    "model": "mimo-v2-flash",
    "timeout_sec": 600,
    "repo_root": "/tmp/test_repo",
    "allowed_paths": ["src/", "tests/"],
    "metadata": {
      "objective": "Test worker execution",
      "requirements": ["Create a simple function"]
    }
  }'
```

**Worker Output:**
```
Job received from backend job_id='...' execution_location='LOCAL_MACHINE'
✅ Job signature verified
Starting job execution...
✅ repo_root validated
✅ All paths validated
✅ TASK.md generated
✅ Roo Code execution completed (simulated)
✅ Results collected
✅ Result uploaded to backend
✅ Cleanup completed
```

---

## 🔒 Security Features

### Ed25519 Signature Verification

Every job is verified before execution:

```python
# In worker/poller.py
verify_job_signature(job, public_key)
# Raises SecurityError if invalid
```

**Security guarantees:**
- ✅ Jobs cannot be tampered with
- ✅ Only Backend can create valid jobs
- ✅ Worker rejects unsigned/invalid jobs

### 6-Layer Path Validation

Following INTEGRATIONS_AND_OPS.md Section 6.1:

1. **Layer 1**: Convert to absolute, resolve symlinks
2. **Layer 2**: Ensure path inside repo_root
3. **Layer 3**: Check forbidden patterns (`../`, `~`)
4. **Layer 4**: System directory blacklist
5. **Layer 5**: Whitelist prefix validation
6. **Layer 6**: Symlink destination validation

**Example:**
```python
validate_path(
    "src/main.py",  # Relative path
    "/home/user/project",  # repo_root
    ["src/", "tests/"]  # Allowed prefixes
)
# Returns: Path("/home/user/project/src/main.py")
```

**Blocked attempts:**
```python
# Path traversal
validate_path("../etc/passwd", ...)  # ❌ SecurityError

# Absolute path
validate_path("/etc/passwd", ...)  # ❌ SecurityError

# Outside allowed prefixes
validate_path("config/secrets.yaml", ...)  # ❌ SecurityError
```

---

## 📁 Worker Structure

```
local_agent_hub/
├── main.py                    # Main entry point
├── __init__.py
├── core/
│   ├── config.py              # agents.yaml loading
│   ├── security.py            # Ed25519 + Path validation ⭐
│   └── __init__.py
├── worker/
│   ├── poller.py              # Long polling ⭐
│   ├── executor.py            # Job execution ⭐
│   └── __init__.py
├── tests/
│   └── test_security.py       # Security tests
├── requirements.txt
└── agents.yaml.example
```

---

## 🔄 Worker Flow

```
1. Poll for jobs (Long polling, 30s timeout)
   ↓
2. Receive job from backend
   ↓
3. ✅ Verify Ed25519 signature
   ↓
4. ✅ Validate all file paths
   ↓
5. Generate TASK.md
   ↓
6. Execute job (Roo Code simulation)
   ↓
7. Collect results (git diff)
   ↓
8. Upload result to backend
   ↓
9. Cleanup artifacts
   ↓
10. Return to step 1
```

---

## 🐛 Troubleshooting

### Worker Can't Connect to Backend
```
Error: Connection refused
```
**Solution**: Ensure backend is running on the configured URL

### Invalid Signature Error
```
🔒 SECURITY VIOLATION: Invalid job signature
```
**Solution**: Ensure `job_signing_public_key` in `agents.yaml` matches backend's public key

### Path Validation Failed
```
🔒 Path validation failed: Path traversal detected
```
**Solution**: Check `allowed_paths` in job request matches `allowed_path_prefixes` in `agents.yaml`

### Configuration Not Found
```
Configuration file not found: agents.yaml
```
**Solution**: Copy `agents.yaml.example` to `agents.yaml` and configure it

---

## 📊 Worker Metrics

The worker logs important metrics:

- **Jobs processed**: Count of completed jobs
- **Signature verifications**: Success/failure rate
- **Path validations**: Blocked attempts
- **Execution time**: Per-job timing
- **Heartbeat status**: Connection health

---

## 🎯 Next Steps

1. **Integrate Real Roo Code**: Replace simulation with actual Roo Code trigger
2. **Add Ollama**: Install and configure Ollama for local LLM
3. **Production Deployment**: Configure for production environment
4. **Monitoring**: Add metrics collection and alerting

---

## 🔗 Related Documentation

- Backend API: http://localhost:8000/docs
- QUICKSTART.md: Backend setup guide
- JOB_AND_SECURITY.md: Job schema and signature specification
- INTEGRATIONS_AND_OPS.md: Path validation and Roo Code integration

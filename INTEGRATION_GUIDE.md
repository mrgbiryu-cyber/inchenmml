# BUJA Core Platform - End-to-End Integration Guide

This guide walks you through starting all services and running your first "Hello World" job.

---

## 📋 Prerequisites

Before starting, ensure you have:

- ✅ Python 3.10+ installed
- ✅ Docker and Docker Compose installed
- ✅ Backend dependencies installed (`backend/requirements.txt`)
- ✅ Worker dependencies installed (`local_agent_hub/requirements.txt`)
- ✅ Ed25519 keys generated

---

## 🔑 Step 0: Generate Keys (One-Time Setup)

### Generate Ed25519 Keys

```bash
cd d:\project\myllm
python scripts/generate_keys.py
```

**Output:**
```
PRIVATE KEY (Backend .env)
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEI...
-----END PRIVATE KEY-----

PUBLIC KEY (Worker agents.yaml)
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA...
-----END PUBLIC KEY-----
```

### Configure Backend

Create `backend/.env`:

```bash
cd backend
copy ..\.env.example .env
```

Edit `backend/.env` and add:

```env
# Required
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secret-key-here-change-this-in-production

# Ed25519 Keys (from generate_keys.py)
JOB_SIGNING_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEI...
-----END PRIVATE KEY-----

JOB_SIGNING_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA...
-----END PUBLIC KEY-----
```

### Configure Worker

Create `local_agent_hub/agents.yaml`:

```bash
cd local_agent_hub
copy agents.yaml.example agents.yaml
```

Edit `local_agent_hub/agents.yaml`:

```yaml
server:
  url: http://localhost:8000
  worker_token: sk_worker_test_token_12345  # Any value for now
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
  # Ed25519 public key (from generate_keys.py)
  job_signing_public_key: |
    -----BEGIN PUBLIC KEY-----
    MCowBQYDK2VwAyEA...
    -----END PUBLIC KEY-----
  
  allowed_path_prefixes:
    - ""  # Allow root-level files for testing
    - "src/"
    - "tests/"
  
  forbidden_absolute_paths:
    - "/etc/"
    - "/root/"
    - "/sys/"
    - "/proc/"
    - "~/.ssh/"
    - "~/.aws/"
```

---

## 🚀 Step 1: Start Redis (Terminal 1)

### Using Docker Compose

```bash
cd d:\project\myllm\docker
docker-compose up -d redis
```

**Verify:**
```bash
docker-compose ps
```

Expected output:
```
NAME           STATUS    PORTS
buja-redis     Up        0.0.0.0:6379->6379/tcp
```

### Alternative: Local Redis

If you have Redis installed locally:
```bash
redis-server
```

---

## 🖥️ Step 2: Start Backend (Terminal 2)

### Activate Virtual Environment

```bash
cd d:\project\myllm\backend
venv\Scripts\activate
```

### Start Backend

```bash
python -m app.main
```

**Expected Output:**
```
INFO:     Starting BUJA Core Platform Backend version=1.0.0
INFO:     Redis connection established url=redis://localhost:6379/0
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Verify Backend

Open browser: http://localhost:8000

You should see:
```json
{
  "name": "BUJA Core Platform",
  "version": "1.0.0",
  "status": "operational",
  "environment": "development"
}
```

API Docs: http://localhost:8000/docs

---

## 🔍 Step 3: Health Check

Open a new terminal and run:

```bash
cd d:\project\myllm
python scripts/health_check.py
```

**Expected Output:**
```
======================================================================
BUJA Core Platform - Health Check
======================================================================

Checking Backend...
✅ Backend: Running
   Status: healthy
   Redis: healthy

Checking Redis...
✅ Redis: Accessible

Checking Authentication...
✅ Authentication: Working

======================================================================
✅ All systems operational!
======================================================================
```

---

## 🤖 Step 4: Start Worker (Terminal 3)

### Activate Virtual Environment

```bash
cd d:\project\myllm\local_agent_hub
venv\Scripts\activate
```

### Start Worker

```bash
python main.py
```

**Expected Output:**
```
2026-01-16T22:10:00 [info     ] 🚀 BUJA Local Worker starting worker_id=worker_001 server_url=http://localhost:8000
2026-01-16T22:10:00 [info     ] Starting job polling loop server_url=http://localhost:8000 poll_interval=5
2026-01-16T22:10:05 [debug    ] Polling timeout (no jobs)
2026-01-16T22:10:10 [debug    ] Polling timeout (no jobs)
```

✅ **Worker is now polling for jobs!**

---

## 🎯 Step 5: Submit Test Job (Terminal 4)

### Run Test Script

```bash
cd d:\project\myllm
python scripts/test_job.py
```

**Expected Output:**

```
======================================================================
BUJA Core Platform - Integration Test
======================================================================

📁 Test directory: C:\Users\PC\AppData\Local\Temp\buja_test

Step 1: Logging in...
✅ Logged in as admin

Step 2: Creating test job...
✅ Job created: 550e8400-e29b-41d4-a716-446655440000
   Status: QUEUED
   Message: Job queued successfully for LOCAL_MACHINE execution

Step 3: Waiting for worker to process job...
   (Worker should poll and execute within 30 seconds)

Step 4: Checking job status...

📊 Job Status:
   Job ID: 550e8400-e29b-41d4-a716-446655440000
   Status: COMPLETED
   Execution Location: LOCAL_MACHINE
   Model: mimo-v2-flash

📝 Result:
{
  "diff": "(Git diff unavailable - no git repository)",
  "files_modified": [],
  "execution_time_ms": 5234
}

Step 5: Verifying file creation...
⚠️  File not found: C:\Users\PC\AppData\Local\Temp\buja_test\hello_buja.txt
   This is expected if using simulated Roo Code
   Check TASK.md was generated in: C:\Users\PC\AppData\Local\Temp\buja_test

======================================================================
✅ Integration Test Complete!
======================================================================
```

---

## 📝 Step 6: Verify Logs

### Backend Logs (Terminal 2)

Look for:
```
INFO:     Job created via API job_id=550e8400-... user_id=user_admin_001 execution_location=LOCAL_MACHINE
INFO:     Job signed successfully job_id=550e8400-...
INFO:     Job created and queued job_id=550e8400-... tenant_id=tenant_hyungnim
```

### Worker Logs (Terminal 3)

Look for:
```
[info     ] Job received from backend job_id=550e8400-... execution_location=LOCAL_MACHINE
[info     ] ✅ Job signature verified job_id=550e8400-...
[info     ] Starting job execution job_id=550e8400-... repo_root=C:\Users\PC\AppData\Local\Temp\buja_test
[info     ] ✅ repo_root validated repo_root=C:\Users\PC\AppData\Local\Temp\buja_test
[info     ] ✅ All paths validated
[info     ] ✅ TASK.md generated path=C:\Users\PC\AppData\Local\Temp\buja_test\TASK.md
[info     ] Simulating Roo Code execution (5s)... job_id=550e8400-...
[info     ] ✅ Completion marker created path=C:\Users\PC\AppData\Local\Temp\buja_test\.roo_completed
[info     ] ✅ Results collected
[info     ] Result uploaded successfully job_id=550e8400-... status=COMPLETED
[info     ] ✅ Cleanup completed
```

---

## 🎉 Success Indicators

### ✅ Backend
- Server started on port 8000
- Redis connection established
- Job created and signed
- Job queued to Redis

### ✅ Worker
- Connected to backend
- Polling for jobs
- Job signature verified
- TASK.md generated
- Result uploaded

### ✅ End-to-End Flow
1. Job created via API ✅
2. Job signed with Ed25519 ✅
3. Job queued to Redis ✅
4. Worker polled and received job ✅
5. Signature verified ✅
6. Paths validated ✅
7. TASK.md generated ✅
8. Execution completed ✅
9. Result uploaded ✅

---

## 🔍 Verification Checklist

### Check TASK.md

Navigate to test directory:
```bash
cd C:\Users\PC\AppData\Local\Temp\buja_test
type TASK.md
```

You should see:
```markdown
# CODING TASK
**Generated by**: BUJA Core Platform  
**Job ID**: `550e8400-...`  

## 🎯 Objective
Create a Hello World file

## 📋 Requirements
1. Create a file named hello_buja.txt
2. Write 'Hello from BUJA Core Platform - Phase 4!' to the file

...
```

### Check Redis

```bash
redis-cli
> KEYS job:*
> GET job:550e8400-...:status
"COMPLETED"
```

### Check Backend API

```bash
curl http://localhost:8000/api/v1/jobs/550e8400-.../status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🐛 Troubleshooting

### Backend Won't Start

**Error**: `Failed to connect to Redis`

**Solution**:
```bash
cd docker
docker-compose up -d redis
docker-compose ps
```

### Worker Can't Connect

**Error**: `Connection refused`

**Solution**: Ensure backend is running on http://localhost:8000

### Invalid Signature

**Error**: `🔒 SECURITY VIOLATION: Invalid job signature`

**Solution**: Ensure public key in `agents.yaml` matches private key in backend `.env`

### Path Validation Failed

**Error**: `Path traversal detected`

**Solution**: Ensure `allowed_path_prefixes` in `agents.yaml` includes `""` for root-level files

---

## 📊 System Architecture Verification

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Backend   │◄────────┤    Redis    │────────►│   Worker    │
│  (Port 8000)│         │  (Port 6379)│         │  (Polling)  │
└─────────────┘         └─────────────┘         └─────────────┘
      │                                                │
      │ 1. Create Job                                 │
      │ 2. Sign (Ed25519)                             │
      │ 3. Queue (RPUSH)                              │
      │                                                │
      │                                 4. Poll (BLPOP)│
      │                                 5. Verify Sig  │
      │                                 6. Validate    │
      │                                 7. Execute     │
      │                                                │
      │◄────────────────────────────────8. Upload─────┤
      │                                   Result       │
```

---

## 🎯 Next Steps

1. **Test with Real Roo Code**: Replace simulation with actual Roo Code integration
2. **Add More Test Cases**: Test different job types and error scenarios
3. **Monitor Performance**: Check execution times and resource usage
4. **Production Setup**: Configure for production environment
5. **Add Neo4j**: Integrate agent configuration and knowledge graph

---

## 📚 Additional Resources

- Backend API Docs: http://localhost:8000/docs
- QUICKSTART.md: Backend setup guide
- WORKER_QUICKSTART.md: Worker setup guide
- JOB_AND_SECURITY.md: Job schema and security specifications
- INTEGRATIONS_AND_OPS.md: Path validation and Roo Code integration

---

**🎉 Congratulations! Your BUJA Core Platform is now operational!**

# 🔑 Configuration Setup Guide

## Generated Keys

The following Ed25519 keys have been generated for your BUJA Core Platform:

### Private Key (Backend)
```
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIM0i6WEByPsP27vc4uCJW8IjBOr0yciXZTGOEW6rueJu
-----END PRIVATE KEY-----
```

### Public Key (Worker)
```
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEASAc8S81M5rIK1j/JWqopQ0EQaRnKTNtD3rQ/aTGYQW4=
-----END PUBLIC KEY-----
```

---

## 📝 Configuration Steps

### Step 1: Update Backend .env

Edit `d:\project\myllm\backend\.env` and add:

```env
JOB_SIGNING_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIM0i6WEByPsP27vc4uCJW8IjBOr0yciXZTGOEW6rueJu
-----END PRIVATE KEY-----

JOB_SIGNING_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEASAc8S81M5rIK1j/JWqopQ0EQaRnKTNtD3rQ/aTGYQW4=
-----END PUBLIC KEY-----
```

### Step 2: Update Worker agents.yaml

Edit `d:\project\myllm\local_agent_hub\agents.yaml` and update the `security` section:

```yaml
security:
  job_signing_public_key: |
    -----BEGIN PUBLIC KEY-----
    MCowBQYDK2VwAyEASAc8S81M5rIK1j/JWqopQ0EQaRnKTNtD3rQ/aTGYQW4=
    -----END PUBLIC KEY-----
  
  allowed_path_prefixes:
    - ""  # Allow root-level files for testing
    - "src/"
    - "tests/"
```

### Step 3: Restart Backend

1. Stop the current backend (Ctrl+C)
2. Restart: `python -m app.main`

### Step 4: Start Worker

```bash
cd d:\project\myllm\local_agent_hub
python main.py
```

---

## ✅ Expected Output

### Backend
```
INFO:     Starting BUJA Core Platform Backend version=1.0.0
INFO:     Redis connection established url=redis://localhost:6379/0
INFO:     Application startup complete
```

### Worker
```
2026-01-16T22:50:00 [info] 🚀 BUJA Local Worker starting
2026-01-16T22:50:00 [info] Starting job polling loop
```

---

## 🧪 Test Integration

After both services are running:

```bash
cd d:\project\myllm
python scripts\test_job.py
```

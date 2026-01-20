Part 2: Job System & Security Details
Continued from Part 1
Focus: Job Specification, Signature, Worker Protocol, Error Handling, Security Audit

[PART 3] Job System (CORE EXECUTION UNIT)
3.1 Job Is the Only Executable Unit
Fundamental Rule:
ALL executions MUST be wrapped in a Job.
NO execution without a Job ID.

Why Jobs?

✅ Auditability: Every action has a trail
✅ Idempotency: Retry-safe with idempotency keys
✅ State Management: Clear lifecycle (QUEUED → RUNNING → COMPLETED/FAILED)
✅ Security: Signature prevents tampering
✅ Resource Control: Timeout, priority, quota enforcement
3.2 Job Schema (COMPLETE SPECIFICATION)
Mandatory Fields:


{
  "job_id": "uuid-v4",           // REQUIRED: Unique identifier
  "tenant_id": "string",         // REQUIRED: Owner tenant
  "user_id": "string",           // REQUIRED: Requesting user
  "execution_location": "LOCAL_MACHINE|CLOUD",  // REQUIRED: Where to run
  "provider": "OPENROUTER|OLLAMA",              // REQUIRED: Which LLM provider
  "model": "mimo-v2-flash",      // REQUIRED: Model name
  "created_at_ts": 1710000000,   // REQUIRED: Unix timestamp (seconds)
  "status": "QUEUED",            // REQUIRED: Current state
  "timeout_sec": 600,            // REQUIRED: Max execution time (1-3600)
  "idempotency_key": "sha256:...", // REQUIRED: Replay prevention
  "signature": "base64:...",     // REQUIRED: Ed25519 signature
  
  // CONDITIONAL: Required if execution_location == LOCAL_MACHINE
  "repo_root": "/home/user/projects/buja",    // Absolute path to project
  "allowed_paths": ["src/", "tests/"],        // Whitelist prefixes
  
  // OPTIONAL: Metadata
  "steps": ["plan", "code", "qa"],          // Workflow phases (informational)
  "priority": 5,                           // 1 (low) to 10 (high), default: 5
  "metadata": {                           // Custom fields
    "request_source": "telegram",
    "user_context": "..."
  }
}
Field Specifications:

Field	Type	Validation	Example
job_id	UUID v4	Must be valid UUID	"550e8400-e29b-41d4-a716-446655440000"
tenant_id	String	3-50 chars, alphanumeric+underscore	"tenant_hyungnim"
user_id	String	3-50 chars	"user_001"
execution_location	Enum	LOCAL_MACHINE | CLOUD	"LOCAL_MACHINE"
provider	Enum	OPENROUTER | OLLAMA	"OLLAMA"
model	String	Must exist in Agent config	"mimo-v2-flash"
created_at_ts	Integer	Unix timestamp (seconds)	1704067200
status	Enum	QUEUED | RUNNING | COMPLETED | FAILED	"QUEUED"
timeout_sec	Integer	1 ≤ value ≤ 3600	600
idempotency_key	String	sha256: + 64 hex chars	"sha256:abc123..."
signature	String	base64: + Ed25519 sig (88 chars)	"base64:SGVsbG8..."
repo_root	String	Absolute path	"/home/user/projects/buja"
allowed_paths	Array	List of prefix strings	["src/", "tests/"]
priority	Integer	1 ≤ value ≤ 10	5
Example Complete Job:


{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "tenant_hyungnim",
  "user_id": "user_001",
  "execution_location": "LOCAL_MACHINE",
  "provider": "OLLAMA",
  "model": "mimo-v2-flash",
  "created_at_ts": 1704067200,
  "status": "QUEUED",
  "timeout_sec": 600,
  "idempotency_key": "sha256:a3f5c8d2e1b4...",
  "signature": "base64:SGVsbG9Xb3JsZA==...",
  "repo_root": "/home/user/projects/buja",
  "allowed_paths": ["src/", "tests/", "docs/"],
  "steps": ["analyze", "code", "test"],
  "priority": 7,
  "metadata": {
    "input": "Add user login endpoint",
    "estimated_files": 3
  }
}
3.3 Job Signature Algorithm (FIXED)
Algorithm Choice: Ed25519 (EdDSA on Curve25519)

Why Ed25519?
✅ Very fast signature verification (~70k verifications/sec)
✅ Small signatures (64 bytes)
✅ Strong security (equivalent to 3072-bit RSA)
✅ No timing attacks
✅ Standard library support (Python: cryptography package)

Key Pair Generation (Backend Setup):


# Generate once during Backend initialization
python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Generate key pair
private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Serialize to PEM format
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

print('PRIVATE KEY (Backend only):')
print(private_pem.decode())

print('\nPUBLIC KEY (Copy to Local Worker):')
print(public_pem.decode())
"
Signature Process (Backend):


from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import json
import base64

def sign_job(job_dict: dict, private_key_pem: str) -> str:
    \"\"\"
    Sign a job with Backend's private key
    
    Args:
        job_dict: Job data (without 'signature' field)
        private_key_pem: Ed25519 private key in PEM format
    
    Returns:
        Base64-encoded signature
    \"\"\"
    # 1. Load private key
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(), password=None
    )
    
    # 2. Create canonical JSON (sorted keys, no whitespace)
    canonical_json = json.dumps(job_dict, sort_keys=True, separators=(',', ':'))
    message = canonical_json.encode('utf-8')
    
    # 3. Sign
    signature_bytes = private_key.sign(message)
    
    # 4. Encode as base64
    signature_b64 = base64.b64encode(signature_bytes).decode('ascii')
    return f\"base64:{signature_b64}\"

# Usage in Job creation:
job = {
    \"job_id\": \"...\",
    \"tenant_id\": \"...\",
    # ... other fields
}

private_key_pem = os.getenv(\"JOB_SIGNING_PRIVATE_KEY\")
signature = sign_job(job, private_key_pem)
job[\"signature\"] = signature

# Now send to Redis queue
await redis.rpush(f\"job_queue:{tenant_id}\", json.dumps(job))
Verification Process (Local Worker):


from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
import json
import base64

def verify_job_signature(job_dict: dict, public_key_pem: str) -> bool:
    \"\"\"
    Verify job signature with Backend's public key
    
    Args:
        job_dict: Complete job including 'signature' field
        public_key_pem: Ed25519 public key in PEM format
    
    Returns:
        True if valid, raises SecurityError if invalid
    \"\"\"
    # 1. Extract signature
    signature_field = job_dict.pop('signature')
    if not signature_field.startswith('base64:'):
        raise SecurityError(\"Invalid signature format\")
    
    signature_b64 = signature_field.replace('base64:', '')
    signature_bytes = base64.b64decode(signature_b64)
    
    # 2. Load public key
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    
    # 3. Recreate canonical message
    canonical_json = json.dumps(job_dict, sort_keys=True, separators=(',', ':'))
    message = canonical_json.encode('utf-8')
    
    # 4. Verify
    try:
        public_key.verify(signature_bytes, message)
        return True
    except InvalidSignature:
        raise SecurityError(
            f\"Job signature verification failed for job_id={job_dict.get('job_id')}\"
        )

# Usage in Local Worker:
received_job = json.loads(job_json)
public_key_pem = config['security']['job_signing_public_key']

try:
    verify_job_signature(received_job, public_key_pem)
    logger.info(f\"✅ Job {received_job['job_id']} signature verified\")
except SecurityError as e:
    logger.error(f\"🔒 Signature verification failed: {e}\")
    await report_security_violation(received_job['job_id'])
    return  # Reject job
Key Distribution:


# Backend .env
JOB_SIGNING_PRIVATE_KEY=|
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIFg3...
-----END PRIVATE KEY-----

# Local Worker agents.yaml
security:
  job_signing_public_key: |
    -----BEGIN PUBLIC KEY-----
    MCowBQYDK2VwAyEAXDe4B9...
    -----END PUBLIC KEY-----
Key Rotation Policy:

Rotation Schedule: Every 90 days
Process:
Generate new key pair (keep old for 14 days)
Update Backend environment variable
Notify Local Worker admins (email)
Workers update public key in agents.yaml
Grace period: Backend signs with old + new keys
After 14 days: Remove old key
Security Note:

Private key NEVER leaves Backend server
Public key can be distributed openly
Compromised public key = No risk (only verifies)
Compromised private key = Emergency rotation (1 hour notice)
3.4 Job Lifecycle & State Transitions
State Machine:


    ┌─────────┐
    │ QUEUED  │ ← Job created by Backend
    └────┬────┘
         │ Worker fetches
         ▼
    ┌─────────┐
    │ RUNNING │ ← Worker starts execution
    └────┬────┘
         │
    ┌────┴────┐
    ▼         ▼
┌──────────┐ ┌────────┐
│COMPLETED │ │ FAILED │
└──────────┘ └────────┘
State Definitions:

State	Description	Next States	Timeout
QUEUED	Waiting in Redis queue	RUNNING or FAILED (timeout)	None (handled by monitoring)
RUNNING	Worker is executing	COMPLETED or FAILED	job.timeout_sec
COMPLETED	Execution succeeded (Terminal state)	N/A	N/A
FAILED	Execution failed (Terminal state)	N/A	N/A
Failure Substates:


class FailureReason(Enum):
    TIMEOUT = "TIMEOUT"                    # Execution exceeded timeout_sec
    SECURITY_VIOLATION = "SECURITY_VIOLATION"  # Signature invalid or path traversal
    EXECUTION_ERROR = "EXECUTION_ERROR"       # Runtime error (e.g., syntax error)
    WORKER_DISCONNECTED = "WORKER_DISCONNECTED" # Worker lost during execution
    INVALID_JOB = "INVALID_JOB"               # Schema validation failed
Storage:


# Redis (Hot, fast access):
job:{job_id}:status             # String: "QUEUED" | "RUNNING" | ...
job:{job_id}:spec              # JSON: Full job spec
job:{job_id}:result            # JSON: Execution result (if completed)
job:{job_id}:started_at        # Timestamp
job:{job_id}:completed_at      # Timestamp

# Neo4j (Cold, audit trail):
(:Job {
  id: $job_id,
  tenant_id: $tenant_id,
  status: "COMPLETED",
  created_at: datetime(),
  completed_at: datetime(),
  execution_time_ms: 12500
})
3.5 Error Handling & Retry Policy
Retry Decision Matrix:

Error Type	Retry?	Max Retries	Backoff	Next Timeout
SECURITY_VIOLATION	❌ No	0	N/A	N/A
INVALID_JOB	❌ No	0	N/A	N/A
TIMEOUT	✅ Yes	1	60s	2x original
EXECUTION_ERROR	✅ Yes	2	30s	Same
WORKER_DISCONNECTED	✅ Yes	3	15s	Same
Retry Implementation:


async def handle_job_failure(job_id: str, reason: FailureReason, error: str):
    job = await get_job(job_id)
    
    # Check if retryable
    if reason in [FailureReason.SECURITY_VIOLATION, FailureReason.INVALID_JOB]:
        await mark_job_failed(job_id, reason, error)
        await notify_admin_security_incident(job_id, reason)
        return
    
    # Check retry count
    retry_count = job.get('retry_count', 0)
    max_retries = RETRY_LIMITS[reason]
    
    if retry_count >= max_retries:
        await mark_job_failed(job_id, f\"{reason}_RETRY_EXHAUSTED\", error)
        return
    
    # Retry logic
    retry_count += 1
    job['retry_count'] = retry_count
    
    # Adjust timeout for TIMEOUT errors
    if reason == FailureReason.TIMEOUT:
        job['timeout_sec'] *= 2
    
    # Backoff delay
    backoff = RETRY_BACKOFF[reason] * retry_count
    await asyncio.sleep(backoff)
    
    # Re-queue
    await redis.rpush(f\"job_queue:{job['tenant_id']}\", json.dumps(job))
    logger.info(f\"♻️ Job {job_id} requeued (attempt {retry_count}/{max_retries})\")
Dead Letter Queue:


# Jobs that fail after all retries
dead_letter_queue:{tenant_id}  # TTL: 7 days (for manual inspection)

await redis.rpush(
    f\"dead_letter_queue:{tenant_id}\",
    json.dumps({
        \"job\": job,
        \"final_error\": error,
        \"failed_at\": datetime.now().isoformat()
    })
)
await redis.expire(f\"dead_letter_queue:{tenant_id}\", 604800)  # 7 days
[PART 4] Local Worker Specification
4.1 Design Principle (Reinforced)
The Worker is a Dumb Executor:


✅ DO:
- Poll for jobs
- Verify signatures
- Validate paths
- Execute commands
- Upload results

❌ DO NOT:
- Decide intent
- Choose models
- Modify job specs
- Access Backend DB
- Make routing decisions
4.2 Worker Configuration (agents.yaml)
Complete Configuration File:


# agents.yaml - Local Worker Configuration
# SECURITY: This file contains sensitive tokens. Protect with file permissions (chmod 600).

server:
  url: https://api.bujacore.com
  worker_token: sk_worker_1234567890abcdef  # From Super Admin
  poll_interval: 5       # Seconds between polls (if no jobs)
  timeout: 30            # Long-polling timeout
  heartbeat_interval: 30 # Health check frequency

capabilities:
  - provider: OLLAMA
    model: mimo-v2-flash
    endpoint: http://localhost:11434
    timeout: 120           # Model inference timeout
    max_concurrent: 3      # Max parallel jobs

security:
  # Ed25519 public key for signature verification
  job_signing_public_key: |
    -----BEGIN PUBLIC KEY-----
    MCowBQYDK2VwAyEAXDe4B9X...
    -----END PUBLIC KEY-----
  
  # Path constraints
  allowed_path_prefixes:
    - "src/"
    - "tests/"
    - "docs/"
  
  # Absolute blacklist (even if in allowed_paths)
  forbidden_absolute_paths:
    - "/etc/"
    - "/root/"
    - "/sys/"
    - "/proc/"
    - "~/.ssh/"
    - "~/.aws/"

execution:
  # Roo Code integration
  roo_code:
    enabled: true
    task_file: "TASK.md"
    completion_marker: ".roo_completed"
  
  # File limits
  max_file_size_bytes: 1048576      # 1 MB per file
  max_total_size_bytes: 10485760    # 10 MB per job

logging:
  level: INFO       # DEBUG | INFO | WARNING | ERROR
  file: logs/worker.log
  max_size_bytes: 10485760  # 10 MB
  backup_count: 5
  format: "[%(asctime)s] %(levelname)s: %(message)s"
4.3 Worker Execution Flow (Step-by-Step)

# Pseudocode for Local Worker main loop
async def worker_main_loop():
    while running:
        # Step 1: Poll for job
        job = await poll_job_from_server()
        if job is None:
            await asyncio.sleep(config['server']['poll_interval'])
            continue
        
        # Step 2: Verify signature
        try:
            verify_job_signature(job, public_key)
        except SecurityError as e:
            await report_security_violation(job['job_id'], str(e))
            continue
        
        # Step 3: Validate paths
        try:
            validate_all_paths(job)
        except SecurityError as e:
            await report_failure(job['job_id'], 'SECURITY_VIOLATION', str(e))
            continue
        
        # Step 4: Update status to RUNNING
        await update_job_status(job['job_id'], 'RUNNING')
        
        # Step 5: Execute job
        try:
            result = await execute_job_sandboxed(job)
            await upload_result(job['job_id'], result)
        except TimeoutError as e:
            await report_failure(job['job_id'], 'TIMEOUT', str(e))
        except Exception as e:
            await report_failure(job['job_id'], 'EXECUTION_ERROR', str(e))

async def execute_job_sandboxed(job: dict) -> dict:
    \"\"\"Execute job with all safety checks\"\"\"
    # 1. Generate TASK.md
    task_path = Path(job['repo_root']) / config['execution']['roo_code']['task_file']
    generate_task_md(job, task_path)
    
    # 2. Trigger Roo Code
    await trigger_roo_code(job['repo_root'])
    
    # 3. Wait for completion (with timeout)
    completion_marker = Path(job['repo_root']) / config['execution']['roo_code']['completion_marker']
    await wait_for_file(completion_marker, timeout=job['timeout_sec'])
    
    # 4. Collect results
    result = await collect_execution_results(job)
    
    # 5. Cleanup
    task_path.unlink(missing_ok=True)
    completion_marker.unlink(missing_ok=True)
    
    return result
4.4 Worker Health Check & Reassignment
Heartbeat Protocol:


# Local Worker sends every 30 seconds
async def send_heartbeat():
    while running:
        await httpx.post(
            f\"{SERVER_URL}/api/v1/workers/heartbeat\",
            headers={\"Authorization\": f\"Bearer {WORKER_TOKEN}\"},
            json={
                \"worker_id\": WORKER_ID,
                \"status\": \"active\",
                \"current_jobs\": [job_id for job_id in running_jobs],
                \"capabilities\": config['capabilities']
            }
        )
        await asyncio.sleep(30)
Backend Monitoring:


# Backend checks worker health
async def monitor_workers():
    while True:
        workers = await get_all_workers()
        for worker in workers:
            last_heartbeat = await redis.get(f\"worker:{worker.id}:last_heartbeat\")
            if not last_heartbeat:
                continue
            
            elapsed = time.time() - float(last_heartbeat)
            
            # Mark inactive if no heartbeat for 2 minutes
            if elapsed > 120:
                await mark_worker_inactive(worker.id)
                await reassign_jobs(worker.id)
        
        await asyncio.sleep(30)

async def reassign_jobs(worker_id: str):
    \"\"\"Reassign jobs from inactive worker\"\"\"
    jobs = await get_running_jobs_by_worker(worker_id)
    
    for job in jobs:
        retry_count = job.get('reassign_count', 0)
        if retry_count >= 2:
            await mark_job_failed(
                job['job_id'],
                'WORKER_DISCONNECTED_RETRY_EXHAUSTED',
                f\"Worker {worker_id} disconnected during execution\"
            )
            continue
        
        # Reset to QUEUED
        job['status'] = 'QUEUED'
        job['reassign_count'] = retry_count + 1
        await redis.rpush(f\"job_queue:{job['tenant_id']}\", json.dumps(job))
        logger.warning(f\"♻️ Job {job['job_id']} reassigned due to worker disconnect\")
[PART 5] Security & Audit
5.1 Audit Logging
Logged Events:


class AuditEventType(Enum):
    # Authentication
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    
    # Worker Management
    WORKER_REGISTERED = "WORKER_REGISTERED"
    WORKER_DEREGISTERED = "WORKER_DEREGISTERED"
    WORKER_TOKEN_ISSUED = "WORKER_TOKEN_ISSUED"
    
    # Job Lifecycle
    JOB_CREATED = "JOB_CREATED"
    JOB_STARTED = "JOB_STARTED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    
    # Security
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    PATH_TRAVERSAL_ATTEMPT = "PATH_TRAVERSAL_ATTEMPT"
    
    # Resource
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMIT_HIT = "RATE_LIMIT_HIT"
Log Format:


{
  "event": "SECURITY_VIOLATION",
  "timestamp": "2025-01-01T10:00:00.123Z",
  "severity": "HIGH",
  "user_id": "user_001",
  "tenant_id": "tenant_001",
  "ip_address": "192.168.1.100",
  "user_agent": "Local-Worker/1.0",
  "details": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "violation_type": "INVALID_SIGNATURE",
    "error": "Ed25519 signature verification failed"
  },
  "context": {
    "endpoint": "/api/v1/jobs/pending",
    "method": "GET"
  }
}
Storage & Retention:


# Hot storage (Redis): 7 days
audit_log:{YYYYMMDD}

# Cold storage (Neo4j): 1 year
(:AuditLog {
  event: "SECURITY_VIOLATION",
  timestamp: datetime(),
  severity: "HIGH",
  ...
})-[:PERFORMED_BY]->(:User {id: $user_id})

# Critical events → Immediate notification
if event.severity == "HIGH":
    await notify_admin_telegram(event)
5.2 Security Response Procedures
Incident Response:

Level 1 (Low Severity):

Invalid login attempts
Rate limit hits
Action: Log only
Level 2 (Medium Severity):

Permission denied
Quota exceeded
Action: Log + Email notification (daily digest)
Level 3 (High Severity):

Invalid job signature
Path traversal attempt
Action:
Log + Immediate Telegram alert
Block worker (if from worker)
Increase monitoring
Level 4 (Critical):

Private key compromise (suspected)
Mass signature failures
Action:
Emergency key rotation (1 hour)
All workers forced offline
Manual inspection required
Configuration Summary
This completes Part 2 (Job & Security).

Key contents:
✅ Complete Job Schema (all fields specified)
✅ Ed25519 Signature Algorithm (implementation code included)
✅ Job Lifecycle & State Machine
✅ Error Handling & Retry Policy (decision matrix)
✅ Local Worker Specification (complete config + flow)
✅ Worker Health Check & Reassignment
✅ Audit Logging (events, format, storage)
✅ Security Response Procedures

Next: Part 3 (Integrations & Operations)
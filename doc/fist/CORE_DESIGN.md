# BUJA Core Platform – Master Specification v3.4
# Part 1: Core Design & Architecture

**문서 버전**: v3.4 (Complete & Hardened)
**업데이트 목적**: Critical Issues 해결, 구현 가능한 완전한 스펙
**대상**: 안티그래비티 시스템 (Design-First, Implementation-Ready)
**작성일**: 2025-01-01
---
## [PART 0] Absolute Architecture Principles (NON-NEGOTIABLE)

### 0.1 Single Orchestrator Rule
**Backend is the ONLY decision maker.**
- ✅ Backend decides: Intent, Permissions, Agent Selection, Workflow
- ❌ Local Worker decides: NOTHING (Executor Only)

### 0.2 Local Worker Absolute Constraints
| Forbidden | Allowed |
|-----------|---------|
| ❌ Decide intent | ✅ Execute signed Jobs |
| ❌ Decide permissions | ✅ Verify signatures |
| ❌ Select models | ✅ Validate paths |
| ❌ Connect to DB/Redis | ✅ Poll for Jobs (HTTPS) |
| ❌ Execute unsigned Jobs | ✅ Upload results |
| ❌ Open inbound ports | ✅ Outbound HTTPS ONLY |

### 0.3 Security First Principle
**Assume Local Worker will eventually be compromised.**
Even if compromised:
- ✅ No cross-tenant damage (Signature prevents tampering)
- ✅ No arbitrary server execution (Path validation)
- ✅ No privilege escalation (RBAC enforced server-side)

### 0.4 Conflict Resolution Rule
**If any ambiguity exists:**
1. Favor Security over Convenience
2. Favor Separation over Integration
3. Favor Explicit over Implicit

---
## [PART 1] Product Requirements Document (PRD)

### 1.1 Product Vision
**BUJA Core Platform** is a **Server-Centric Hybrid AI Platform** that orchestrates:
- **Cloud LLMs** (via OpenRouter: DeepSeek, Claude, Gemini)
- **Local LLMs** (via Ollama: MiMo-V2-Flash on owner's PC)

**Decision Model:**
- Backend determines **"WHAT to do"** (Intent, Agent, Workflow)
- Local Worker executes **"HOW to do it"** (Job execution)

**Core Principle:**
- Backend = Single Source of Truth
- Local Worker = Stateless, Replaceable Executor

---
### 1.2 Target Users (Actors)

#### Actor 1: Super Admin (Owner)
**Capabilities:**
- Register/Deregister Local Workers
- Access cross-tenant data (with explicit audit)
- Configure Agent Roles in Neo4j
- Issue Worker Tokens

**Constraints:**
- Must use MFA for sensitive operations
- All actions logged in Audit Log

---
#### Actor 2: SaaS Tenant (End User)
**Capabilities:**
- Use Cloud LLMs via API Key/JWT
- Create/Query Knowledge (isolated to own tenant)
- View own usage quota

**Constraints:**
- ❌ CANNOT trigger Local Execution
- ❌ CANNOT access other tenant's data
- Limited to monthly quota ($100 default)

---
#### Actor 3: Local Worker (The Hands)
**Capabilities:**
- Poll for pending Jobs (Outbound HTTPS)
- Execute signed Jobs in sandboxed environment
- Upload execution results

**Constraints:**
- ❌ NO decision-making logic
- ❌ NO direct DB/Redis access
- ❌ NO inbound network ports
- ✅ ONLY accepts cryptographically signed Jobs

---
#### Actor 4: The Gardener (System Agent)
**Role:**
- Background knowledge archiving
- Web search integration
- Pattern learning from successful Jobs

**Execution:**
- Runs inside Backend (NOT a separate service)
- Async task queue (Celery or Redis Queue)

---
### 1.3 Core Functional Requirements

#### FR-001: Strict Authentication (Server-Side Only)
**HTTP/Web API:**
Authentication: JWT (Bearer Token) ONLY
Claims: {sub: user_id, tenant_id: string, role: enum}
Validation: EVERY endpoint uses Depends(get_current_user)

**Telegram:**
```yaml
Flow: One-Time Link
Steps:
  1. User sends /start to Bot
  2. Backend generates one-time link (5min TTL)
     - Redis: {token: chat_id, ttl: 300}
  3. User clicks link in browser
  4. Backend maps chat_id ↔ user_id (permanent, DB)
  5. Future messages:
     - Backend receives chat_id from Telegram
     - Internal lookup: user_id = get_user_by_chat_id(chat_id)
     - Internal JWT generated for permission check
     - Response sent to chat_id

Local Worker:
Authentication: Worker Token (sk_worker_...)
Issued by: Super Admin ONLY
Scope: job:fetch, job:submit_result
Validation: Signature on each Job (Ed25519)

Header Trust Policy:


# ❌ NEVER trust these for authentication:
X-Service-ID      # Routing hint only
X-User-ID         # Spoofable
X-Tenant-ID       # Spoofable

# ✅ ONLY trust:
Authorization: Bearer <JWT>  # For users
Authorization: Bearer <WorkerToken>  # For workers
FR-002: RBAC & Multi-Tenancy
Role Hierarchy:


class UserRole(Enum):
    SUPER_ADMIN = "super_admin"    # All permissions + Worker control
    TENANT_ADMIN = "tenant_admin"  # Manage own tenant users
    STANDARD_USER = "standard_user" # Use Cloud APIs only
Data Isolation:


# EVERY database query MUST include:
WHERE tenant_id = $tenant_id 
  AND user_id = $user_id  # (if user-scoped)

# Pinecone namespace:
namespace = f"{tenant_id}_{user_id}"

# Neo4j:
MATCH (n:Node {tenant_id: $tenant_id})
Local Execution Policy:


if job.execution_location == "LOCAL_MACHINE":
    if user.role != UserRole.SUPER_ADMIN:
        raise PermissionDenied("LOCAL execution requires SUPER_ADMIN")
FR-003: Agent Configuration (Single Source of Truth)
Storage Division:

Data Type	Storage	Purpose
Business Logic	Neo4j	Agent Role, System Prompt, Model Name, Provider Type
Runtime Config	agents.yaml (Local)	Ollama Endpoint, Port, API Keys
Example:


// Neo4j: Business Policy (Backend manages)
CREATE (coder:AgentRole {
  id: 'agent_coder_001',
  name: 'Coder',
  model: 'mimo-v2-flash',
  provider: 'OLLAMA',  // Type only
  system_prompt: '당신은 Python 전문 코더입니다...',
  cost_per_1k_tokens: 0.0
})

# agents.yaml: Runtime Connection (Local Worker reads)
capabilities:
  - provider: OLLAMA
    model: mimo-v2-flash
    endpoint: http://localhost:11434
    timeout: 120
Terminology (FIXED):


class ProviderType(Enum):
    OPENROUTER = "OPENROUTER"  # Cloud API
    OLLAMA = "OLLAMA"          # Local LLM

class ExecutionLocation(Enum):
    CLOUD = "CLOUD"                    # Backend executes immediately
    LOCAL_MACHINE = "LOCAL_MACHINE"    # Job sent to Local Worker
FR-004: Central Dispatching
Decision Logic Location:


backend/services/dispatcher.py  # ONLY HERE
Intent Categories:


class Intent(Enum):
    CODING = "CODING"          # → LOCAL_MACHINE (if Super Admin)
    PLANNING = "PLANNING"      # → CLOUD
    CHAT = "CHAT"              # → CLOUD
    CODE_REVIEW = "CODE_REVIEW" # → CLOUD
Dispatcher Workflow:


async def dispatch_request(user_input: str, user: User) -> Response:
    # Step 1: Analyze intent
    intent = await classify_intent(user_input)
    
    # Step 2: Check permissions
    if intent == Intent.CODING:
        if user.role != UserRole.SUPER_ADMIN:
            intent = Intent.PLANNING  # Fallback to planning
            notify_user("⚠️ LOCAL execution requires admin. Generated plan instead.")
    
    # Step 3: Route
    if intent == Intent.CODING:
        job_id = await create_job(user, input, location="LOCAL_MACHINE")
        return {"job_id": job_id, "status": "queued"}
    else:
        result = await execute_cloud_llm(intent, user_input)
        return {"result": result}
FR-005: Quota & Cost Tracking
Tracking Keys:


(tenant_id, user_id, provider, model, date)
Storage:


Redis (Hot): usage:{tenant_id}:{provider}:{YYYYMMDD}
Neo4j (Cold): (:UsageLog {tenant_id, user_id, cost, tokens, timestamp})
Cost Rules:


# Cloud (OpenRouter)
cost = (input_tokens + output_tokens) / 1000 * model_price

# Local (Ollama)
cost = 0.0  # Free, but log execution_time_ms
Idempotency:


# Prevent double-billing on retries
idempotency_key = sha256(f"{user_id}_{input}_{timestamp}")
if await redis.exists(f"idempotency:{key}"):
    return cached_result
FR-006: Outbound-Only Local Execution
Network Constraints:


Inbound: ALL DENIED (Firewall rule)
Outbound: HTTPS to api.bujacore.com ONLY

Allowed Methods:
  - GET /api/v1/jobs/pending      # Long polling
  - POST /api/v1/jobs/{id}/result  # Upload result
  - POST /api/v1/workers/heartbeat # Health check

Forbidden:
  - app.listen()
  - socket.bind()
  - Any inbound port opening
Polling Mechanism:


# Local Worker
while True:
    response = await httpx.get(
        f"{SERVER_URL}/api/v1/jobs/pending",
        headers={"Authorization": f"Bearer {WORKER_TOKEN}"},
        timeout=30  # Long polling
    )
    
    if response.status_code == 200:
        job = response.json()
        await execute_job(job)
    elif response.status_code == 204:
        await asyncio.sleep(5)  # No jobs, wait
FR-007: Sandboxed Execution
Path Constraints:


# Job specifies:
job = {
    "repo_root": "/home/user/projects/buja",
    "allowed_paths": ["src/", "tests/", "docs/"]
}

# Validator checks:
def validate_path(file_path: str, repo_root: str, allowed: list) -> Path:
    abs_path = (Path(repo_root) / file_path).resolve()
    
    # Check 1: Inside repo_root?
    if not str(abs_path).startswith(str(Path(repo_root).resolve())):
        raise SecurityError("Path traversal detected")
    
    # Check 2: In allowed prefix?
    relative = abs_path.relative_to(repo_root)
    if not any(str(relative).startswith(p) for p in allowed):
        raise SecurityError(f"Path not in allowed: {allowed}")
    
    return abs_path
Forbidden Paths (Absolute Blacklist):


FORBIDDEN_PATHS = [
    "/etc/", "/root/", "/sys/", "/proc/", "/boot/",
    "~/.ssh/", "~/.aws/", "~/.kube/"
]

[PART 2] Architecture & Technical Design
2.1 System Overview
Architecture Style:


Server-Orchestrated / Worker-Executed
Responsibilities:

Component	Decides	Executes
Backend	Intent, Agent, Workflow, Permissions	Cloud LLM calls
Local Worker	NOTHING	Job execution
2.2 Tech Stack (Design Level)
Layer	Technology	Purpose
Core Backend	FastAPI 0.109+	Async API server
Orchestration	LangGraph 0.0.20+	Multi-agent workflow
Authentication	PyJWT 2.8+	JWT generation/validation
Job Queue	Redis 7.2+	State + Queue
Graph DB	Neo4j 5.x	Knowledge graph
Vector DB	Pinecone	Embeddings (RAG)
Cloud LLM	OpenRouter	DeepSeek, Claude, Gemini
Local LLM	Ollama	MiMo-V2-Flash
Worker Client	httpx 0.27+	Outbound polling
IDE Integration	Roo Code (VS Code)	Code generation
2.3 End-to-End Flow (The Loop)

┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Request & Routing (Server-Side)                   │
└─────────────────────────────────────────────────────────────┘
   User Input (Telegram/Web)
        ↓
   [Gateway] JWT Validation
        ↓
   [Dispatcher] Intent Analysis
        ↓
   ┌─────────────┬─────────────────┐
   │ CLOUD       │ LOCAL_MACHINE   │
   │ (Immediate) │ (Job Queue)     │
   └─────────────┴─────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Execution (Async for LOCAL)                       │
└─────────────────────────────────────────────────────────────┘
   Redis Queue: job_queue:{tenant_id}
        ↓
   [Local Worker] Poll (Outbound HTTPS)
        ↓
   [Local Worker] Verify Signature
        ↓
   [Local Worker] Validate Paths
        ↓
   [Local Worker] Execute (Ollama + Roo Code)
        ↓
   [Local Worker] Upload Result

┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Completion & Knowledge                            │
└─────────────────────────────────────────────────────────────┘
   [Backend] Update Status (Redis → Neo4j)
        ↓
   [Backend] Send Notification (Telegram/Web)
        ↓
   [Gardener] Archive Successful Patterns (Neo4j/Pinecone)
2.4 Provider & Execution Model (STANDARDIZED)
Terminology (FIXED from v3.3):


# ProviderType: WHO provides the model
class ProviderType(Enum):
    OPENROUTER = "OPENROUTER"  # Cloud API (DeepSeek, Claude, Gemini)
    OLLAMA = "OLLAMA"          # Local LLM server

# ExecutionLocation: WHERE the execution happens
class ExecutionLocation(Enum):
    CLOUD = "CLOUD"                    # Backend runs immediately
    LOCAL_MACHINE = "LOCAL_MACHINE"    # Job sent to Worker

# Mapping (Business Rule):
PROVIDER_TO_LOCATION = {
    ProviderType.OPENROUTER: ExecutionLocation.CLOUD,
    ProviderType.OLLAMA: ExecutionLocation.LOCAL_MACHINE
}
Agent Configuration Example:


// Planner (Cloud)
CREATE (planner:AgentRole {
  name: 'Planner',
  model: 'deepseek-chat',
  provider: 'OPENROUTER',
  execution_location: 'CLOUD'
})

// Coder (Local)
CREATE (coder:AgentRole {
  name: 'Coder',
  model: 'mimo-v2-flash',
  provider: 'OLLAMA',
  execution_location: 'LOCAL_MACHINE'
})
2.5 Job Queue Model
Ownership:


Backend ONLY
Local Worker = Read-Only Consumer
Queue Structure:


Redis Key: job_queue:{tenant_id}
Type: List (FIFO)
Operations:
  - RPUSH (Backend adds job)
  - BLPOP (Worker fetches, blocking with 30s timeout)
Job Lifecycle:


State Machine:
  QUEUED → RUNNING → COMPLETED
                  └→ FAILED

Transitions:
  - QUEUED: Backend creates job
  - RUNNING: Worker starts execution
  - COMPLETED: Worker uploads success result
  - FAILED: Worker uploads error OR timeout
2.6 API Design (Conceptual)
Authentication:


POST /api/v1/auth/login
Request: {username, password}
Response: {access_token (JWT), expires_in: 86400}

POST /api/v1/auth/telegram/link
Request: {chat_id}
Response: {link: "https://...", expires_at}
Job Management:


POST /api/v1/jobs
Headers: Authorization: Bearer <USER_JWT>
Request: {input, type}
Response: {job_id, status: "queued"} (202 Accepted)

GET /api/v1/jobs/pending
Headers: Authorization: Bearer <WORKER_TOKEN>
Response: Job JSON (200) or No Content (204)

POST /api/v1/jobs/{id}/result
Headers: Authorization: Bearer <WORKER_TOKEN>
Request: {status, output, error}
Response: {message: "Result uploaded"} (200)

GET /api/v1/jobs/{id}/status
Headers: Authorization: Bearer <USER_JWT>
Response: {job_id, status, progress, created_at}
Health Check:


POST /api/v1/workers/heartbeat
Headers: Authorization: Bearer <WORKER_TOKEN>
Request: {worker_id, status: "active"}
Response: {acknowledged: true}
[PART 3] Security & Configuration
3.1 Secrets Management
Backend Environment Variables:


# Database
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
NEO4J_URL=bolt://...
PINECONE_API_KEY=pk-...

# LLM Providers
OPENROUTER_API_KEY=sk-or-...

# Authentication
JWT_SECRET_KEY=<random-256-bit>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Job Signing (Ed25519)
JOB_SIGNING_PRIVATE_KEY=<ed25519-private-base64>
Local Worker Configuration:


# agents.yaml
server:
  url: https://api.bujacore.com
  worker_token: sk_worker_...  # From Super Admin

security:
  # Ed25519 public key (copy from Backend)
  job_signing_public_key: |
    -----BEGIN PUBLIC KEY-----
    MCowBQYDK2VwAyEA...
    -----END PUBLIC KEY-----
Forbidden:


# ❌ NEVER do this:
API_KEY = "sk-1234567890"  # Hardcoded secret
password = "admin123"      # Hardcoded password

# ✅ ALWAYS do this:
API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    raise ConfigurationError("Missing API key")
3.2 Rate Limiting
Configuration:


RATE_LIMITS = {
    "api": {
        "per_tenant": "100/minute",
        "per_user": "10/second"
    },
    "worker": {
        "job_fetch": "unlimited",  # Polling is safe
        "result_upload": "100/minute"
    },
    "job_queue": {
        "max_queued_per_tenant": 50  # Prevent queue flooding
    }
}
Implementation (Conceptual):


from fastapi import Request, HTTPException
import asyncio

async def rate_limit_middleware(request: Request, call_next):
    user = request.state.user
    key = f"rate_limit:{user.tenant_id}:{request.url.path}:{minute}"
    
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    
    if count > 100:
        raise HTTPException(429, "Rate limit exceeded")
    
    return await call_next(request)
3.3 Cost Quota
Per-Tenant Limits:


DEFAULT_MONTHLY_QUOTA = 100.0  # USD

async def check_quota(tenant_id: str, estimated_cost: float):
    month_key = f"usage:{tenant_id}:{YYYYMM}"
    current = await redis.hget(month_key, "total_cost") or 0
    
    if float(current) + estimated_cost > MONTHLY_QUOTA:
        raise QuotaExceededError(
            f"Monthly quota ${MONTHLY_QUOTA} exceeded. "
            f"Current: ${current}, Requested: ${estimated_cost}"
        )
Configuration Summary
This completes Part 1 (Core Design).

Key contents:
✅ Absolute Principles (Non-negotiable rules)
✅ Product Vision & Actors (Who uses what)
✅ Core Requirements (FR-001 to FR-007, all clarified)
✅ System Architecture (Flow, Tech Stack, Terminology)
✅ API Design (Conceptual endpoints)
✅ Security Basics (Secrets, Rate Limits, Quotas)

Next: Part 2 (Job & Security Details)
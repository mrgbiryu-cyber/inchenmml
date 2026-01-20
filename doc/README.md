# BUJA Core Platform

**Version**: 1.0.0  
**Architecture**: Server-Centric Hybrid AI Platform  
**Status**: Initial Setup Complete

---

## 🎯 Overview

BUJA Core Platform is a **Server-Orchestrated Hybrid AI Platform** that intelligently routes requests between:
- **Cloud LLMs** (via OpenRouter: DeepSeek, Claude, Gemini)
- **Local LLMs** (via Ollama: MiMo-V2-Flash)

### Core Principles
- **Backend = The Brain**: Single source of truth for all decisions (intent, permissions, agent selection)
- **Local Worker = The Hands**: Stateless executor that only runs cryptographically signed jobs
- **Security First**: Zero-trust architecture with Ed25519 signatures and path validation

---

## 📁 Project Structure

```
myllm/
├── backend/                    # FastAPI Backend (The Brain)
│   ├── app/
│   │   ├── core/              # Config, Security, Constants
│   │   ├── api/v1/            # REST API Endpoints
│   │   ├── services/          # Business Logic (Dispatcher, JobManager)
│   │   └── models/            # Pydantic Schemas & DB Models
│   └── requirements.txt
│
├── local_agent_hub/           # Local Worker (The Hands)
│   ├── core/                  # Config, Path Validator
│   ├── worker/                # Poller, Executor
│   ├── requirements.txt
│   └── agents.yaml.example
│
├── shared/                    # Shared Utilities
│   └── (cryptography utils, common schemas)
│
├── docker/                    # Docker Compose
│   └── (Redis, Neo4j, Pinecone emulation)
│
├── .env.example              # Backend Environment Variables
└── README.md                 # This file
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Redis 7.2+
- Neo4j 5.x
- Pinecone account
- Ollama (for local LLM)

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp ../.env.example .env
# Edit .env with your actual credentials
```

### 2. Local Worker Setup

```bash
cd local_agent_hub
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure worker
cp agents.yaml.example agents.yaml
# Edit agents.yaml with your worker token and public key
```

### 3. Generate Ed25519 Keys

```bash
python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

print('PRIVATE KEY (Backend .env):')
print(private_pem.decode())
print('\nPUBLIC KEY (Worker agents.yaml):')
print(public_pem.decode())
"
```

---

## 🔒 Security Architecture

### Authentication
- **Web/API**: JWT Bearer tokens (24h expiry)
- **Telegram**: One-time link → chat_id mapping
- **Worker**: Worker tokens (sk_worker_...) issued by Super Admin

### Job Signing
- **Algorithm**: Ed25519 (EdDSA)
- **Backend**: Signs all jobs with private key
- **Worker**: Verifies signatures with public key
- **Purpose**: Prevents job tampering, even if worker is compromised

### Path Validation
All file operations go through 6-layer validation:
1. Absolute path resolution
2. Repo root containment check
3. Forbidden pattern detection
4. System directory blacklist
5. Whitelist prefix validation
6. Symlink destination validation

---

## 🏗️ Architecture Principles (NON-NEGOTIABLE)

### 0.1 Single Orchestrator Rule
- ✅ Backend decides: Intent, Permissions, Agent Selection, Workflow
- ❌ Local Worker decides: NOTHING (Executor Only)

### 0.2 Local Worker Constraints
| Forbidden | Allowed |
|-----------|---------|
| ❌ Decide intent | ✅ Execute signed Jobs |
| ❌ Decide permissions | ✅ Verify signatures |
| ❌ Select models | ✅ Validate paths |
| ❌ Connect to DB/Redis | ✅ Poll for Jobs (HTTPS) |
| ❌ Execute unsigned Jobs | ✅ Upload results |
| ❌ Open inbound ports | ✅ Outbound HTTPS ONLY |

### 0.3 Security First
Even if Local Worker is compromised:
- ✅ No cross-tenant damage (Signature prevents tampering)
- ✅ No arbitrary server execution (Path validation)
- ✅ No privilege escalation (RBAC enforced server-side)

---

## 📚 Documentation

Refer to the specification documents:
1. **CORE_DESIGN.md**: Architecture, API Design, Core Requirements
2. **JOB_AND_SECURITY.md**: Job Schema, Signature Algorithm, Worker Protocol
3. **INTEGRATIONS_AND_OPS.md**: File Safety, Roo Code Integration, Forbidden Patterns

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Core Backend | FastAPI 0.109+ | Async API server |
| Orchestration | LangGraph 0.0.20+ | Multi-agent workflow |
| Authentication | PyJWT 2.8+ | JWT generation/validation |
| Job Queue | Redis 7.2+ | State + Queue |
| Graph DB | Neo4j 5.x | Knowledge graph |
| Vector DB | Pinecone | Embeddings (RAG) |
| Cloud LLM | OpenRouter | DeepSeek, Claude, Gemini |
| Local LLM | Ollama | MiMo-V2-Flash |
| Worker Client | httpx 0.27+ | Outbound polling |
| IDE Integration | Roo Code (VS Code) | Code generation |

---

## 👥 Actors

### 1. Super Admin (Owner)
- Register/Deregister Local Workers
- Issue Worker Tokens
- Access cross-tenant data (with audit)
- Configure Agent Roles

### 2. SaaS Tenant (End User)
- Use Cloud LLMs via API
- Create/Query Knowledge (isolated)
- View usage quota
- ❌ CANNOT trigger Local Execution

### 3. Local Worker (The Hands)
- Poll for pending Jobs
- Execute signed Jobs
- Upload results
- ❌ NO decision-making logic

### 4. The Gardener (System Agent)
- Background knowledge archiving
- Web search integration
- Pattern learning from successful Jobs

---

## 📝 Next Steps

1. **Implement Core Backend**:
   - Authentication system (JWT, Telegram)
   - Job queue and dispatcher
   - Agent configuration (Neo4j)
   - API endpoints

2. **Implement Local Worker**:
   - Job poller
   - Signature verification
   - Path validator
   - Roo Code integration

3. **Setup Infrastructure**:
   - Docker Compose for Redis, Neo4j
   - Pinecone index creation
   - Ollama installation

4. **Security & Operations**:
   - Audit logging
   - Rate limiting
   - Quota management
   - Health monitoring

---

## 📄 License

Proprietary - All Rights Reserved

---

## 📧 Contact

For questions or support, contact the development team.

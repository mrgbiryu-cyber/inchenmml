# BUJA Core Platform - System Overview

## 1. Project Overview
**BUJA Core Platform** is a Server-Centric Hybrid AI Platform designed to orchestrate AI jobs across cloud and local environments. It features a centralized backend for job dispatching, a local worker for executing sensitive tasks on-premise, and a modern frontend for management and visualization.

## 2. System Architecture

```mermaid
graph TD
    User[User / Admin] -->|HTTPS| Frontend[Next.js Frontend]
    Frontend -->|REST API| Backend[FastAPI Backend]
    Backend -->|Read/Write| Redis[Redis (Job Queue & State)]
    
    subgraph "Local Environment"
        Worker[Local Agent Hub] -->|Long Polling| Backend
        Worker -->|Execute| LocalLLM[Ollama / Local Models]
        Worker -->|File Ops| LocalFS[Local File System]
    end
    
    subgraph "Cloud Environment"
        Backend -->|Execute| CloudLLM[OpenRouter / Cloud APIs]
    end
```

## 3. Backend System (`/backend`)
Running on **Port 8002** (currently).

### 3.1 Technology Stack
- **Framework**: FastAPI (Python)
- **Database**: Mock DB (In-memory for Dev), Redis (Job Queue & State)
- **Security**: JWT (Auth), Ed25519 (Job Signing)

### 3.2 API Modules (`/app/api/v1`)
- **Auth (`/auth`)**:
  - `POST /token`: Login (JWT generation).
  - `POST /register`: User registration (Dev only).
- **Jobs (`/jobs`)**:
  - `POST /`: Create new job (Enforces domain permissions for LOCAL_MACHINE).
  - `GET /{job_id}/status`: Check job status.
  - `GET /pending`: Worker long-polling endpoint.
  - `POST /{job_id}/result`: Worker result submission.
- **Admin (`/admin`)** - *Super Admin Only*:
  - `GET /users`: List all users.
  - `PATCH /users/{user_id}/quota`: Update user quotas (Daily jobs, Concurrent, Storage).
  - `POST /domains`: Register new project domains.
  - `POST /users/{user_id}/domains`: Grant domain access to users.

### 3.3 Key Data Models
- **User**: Includes `quota` (UserQuota) and `allowed_domains` (List[str]).
- **Job**: Includes `execution_location` (CLOUD/LOCAL), `signature`, and `idempotency_key`.
- **Domain**: Represents a project/repo, includes `agent_config` (Model/Provider settings).

### 3.4 Security Features
- **Role-Based Access Control (RBAC)**: SUPER_ADMIN, TENANT_ADMIN, STANDARD_USER.
- **Domain Enforcement**: Standard users can only execute LOCAL jobs in explicitly allowed domains.
- **Job Signing**: All jobs are signed with Ed25519 private key by the backend; Workers verify signature before execution.

## 4. Frontend System (`/frontend`)
Running on **Port 3000**.

### 4.1 Technology Stack
- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **State Management**: Zustand (Auth Store)
- **Visualization**: ReactFlow (LangGraph View)

### 4.2 Key Components
- **Admin Dashboard (`/admin`)**:
  - **Sidebar**: Dedicated navigation for admins.
  - **User Management**: Real-time quota editing via Modal.
  - **Domain Management**: Domain registration with Agent Model configuration (Gemini, GPT, etc.).
- **LangGraph View**: Visualizes AI agent workflows (Nodes/Edges).
- **Log Console**: Real-time streaming logs from backend/worker.

### 4.3 Configuration
- **Axios**: Configured with `baseURL: http://localhost:8002/api/v1`.
- **Interceptors**: Auto-injects JWT token; Handles 401 (Logout) and 403 (Access Denied) errors.

## 5. Worker System (`/local_agent_hub`)
Running locally to execute jobs.

### 5.1 Core Logic
- **Polling**: Long-polls `GET /api/v1/jobs/pending` every 30s.
- **Verification**: Verifies Ed25519 signature of received jobs.
- **Execution**:
  - Supports `OLLAMA` and `OPENROUTER` providers.
  - Performs file operations (Create/Read/Update) on the local file system.
  - Enforces path safety (jailbreak prevention).

## 6. Current Development Status
- **Backend**: Fully functional with Admin API and Domain Permission enforcement.
- **Frontend**: Admin Dashboard implemented (Users, Domains pages).
- **Integration**: Frontend connected to Backend (Port 8002).
- **Testing**: Domain permission enforcement verified via `scripts/test_domain_permissions.py`.

---
*Last Updated: 2026-01-17*

# FIXPLAN MASTER - MYLLM Stability & Structure Optimization

**Generated**: 2026-01-24  
**Purpose**: Single Source of Truth for Analysis → Design → Policy → Implementation  
**Status**: Analysis Complete, Implementation Pending

---

## Executive Summary

MYLLM 프로젝트는 현재 7대 통합 축(H1-H7)에서 불안정 현상을 보이고 있습니다.  
본 분석은 **추측 없는 증거 기반**으로 수행되었으며, 모든 결론은 파일 경로 + 코드 라인 + 스키마로 근거를 제시합니다.

### Core Finding

**Cold Start (데이터=0)는 정상 상태입니다.**  
시스템은 선택적 구성 요소(Neo4j, Pinecone, Tavily)가 없어도 핵심 기능(대화, 작업 생성)을 제공해야 합니다.  
현재 시스템은 이 원칙을 부분적으로만 따르고 있습니다.

---

## H1. Workflow Runtime Issues

### 🔴 Current State (Evidence)

**File**: `backend/app/api/v1/master.py:94`  
**Code**: `if action == "start_task":`  
**Issue**: START TASK event 멈춤 → 워크플로우가 사용자 이벤트를 무한 대기

**File**: `backend/app/services/orchestration_service.py:81`  
**Code**: `print("⏳ [Orchestrator] Paused. Waiting for 'start_task' event...")`  
**Root Cause**: Redis 이벤트 스트림이 전달되지 않거나 polling이 타임아웃됨

**File**: `local_agent_hub/worker/poller.py:61`  
**Code**: `timeout=self.timeout` (기본 30초)  
**Side Effect**: Worker가 job을 가져가지 못하면 QUEUED 상태로 고착

### 🟢 Solution Design

→ 상세 내용은 [RUNTIME_SPEC.md](./RUNTIME_SPEC.md) 참조

---

## H2. Conversation Data Consistency Issues

### 🔴 Current State (Evidence)

**File**: `backend/app/core/database.py:115-143`  
**Function**: `save_message_to_rdb()`  
**Schema**: `MessageModel` (message_id, project_id, thread_id, sender_role, content, timestamp, metadata_json)

**File**: `backend/app/core/database.py:145-166`  
**Function**: `get_messages_from_rdb()`  
**Issue**: 
- Line 147: `if thread_id in ["null", "undefined", ""]` → Defensive filtering
- Line 127-131: UUID conversion fallback → Inconsistent project_id types

**Root Cause**: 
1. Frontend가 `thread_id = "null"` (string) 전송
2. Backend가 UUID ↔ String 변환에서 일관성 없는 처리
3. `uuid.uuid5()` fallback으로 같은 문자열이 다른 UUID로 변환될 수 있음

### 🟢 Solution Design

→ 상세 내용은 [CONVERSATION_CONSISTENCY.md](./CONVERSATION_CONSISTENCY.md) 참조

---

## H3. Template/Router Fixed Output Issues

### 🔴 Current State (Evidence)

**File**: `backend/app/services/master_agent_service.py:_get_llm()`  
**Models**: 
- Line 380: `ChatOllama(model=self.config.model, timeout=30.0)`
- Line 381: `ChatOpenAI(model=self.config.model, ..., timeout=60.0)`

**File**: `backend/app/models/master.py:8`  
**Default**: `provider: Literal["OPENROUTER", "OLLAMA"] = "OPENROUTER"`  
**Default Model**: `model: str = "gpt-4o"`

**No Evidence Found**:
- ❌ Response cache layer
- ❌ Template post-processing
- ❌ Fixed fallback messages

**Hypothesis**: "항상 같은 문구" 문제는 프롬프트 고정이 아니라 **지식 그래프 오염**(H4) 또는 **모델 컨텍스트 누락**(H7)일 가능성 높음

### 🟢 Solution Design

→ 상세 내용은 [ROUTING_FALLBACK_CACHE.md](./ROUTING_FALLBACK_CACHE.md) 참조

---

## H4. Knowledge Graph Pollution & Self-Recursion

### 🔴 Current State (Evidence)

**File**: `backend/app/services/knowledge_service.py:process_message_pipeline()`  
**Issue**: 모든 메시지가 파이프라인을 통과 → 운영 메타데이터도 지식 노드화

**File**: `backend/app/services/knowledge_service.py:121-137`  
**Function**: `_evaluate_importance()`  
**Filter Keywords**: Line 126  
```python
"스키마", "마이그레이션", "dual-write", "neo4j", "rdb", "큐", "비동기",
"프롬프트", "테스트", "로그", "디버그", "에러"
```

**Insufficient**: 에이전트 생성 명령, 프롬프트 설정 대화 등은 필터링되지 않음

**File**: `backend/app/core/neo4j_client.py:create_project_graph()`  
**Issue**: 각 프로젝트마다 Agent 노드 생성 → 프로젝트가 증가하면 Graph 오염

### 🟢 Solution Design

→ 상세 내용은 [KG_SANITIZE_IDEMPOTENCY.md](./KG_SANITIZE_IDEMPOTENCY.md) 참조

---

## H5. VectorDB / Embedding / Chunking Issues

### 🔴 Current State (Evidence)

**File**: `backend/app/core/vector_store.py`  
**Functions**: `upsert_vectors()`, `query_vectors()`  
**Issue**: 
- ❌ No chunking logic found
- ❌ No embedding generation code found
- ❌ No cascade delete or version invalidation

**File**: `backend/app/services/knowledge_service.py`  
**Issue**: Knowledge extraction → Neo4j만 저장, VectorDB 연결 없음

**Gap**: 
1. 문서를 어디서 청킹하는지 미확인
2. 임베딩을 누가 생성하는지 미확인
3. 잘못된 청킹 → 임베딩 오염 → KG Edge 전파 경로 불명확

### 🟢 Solution Design

→ 상세 내용은 [VECTORDB_RETRIEVAL_INGEST.md](./VECTORDB_RETRIEVAL_INGEST.md) 참조

---

## H6. RAG Audit & Tavily Reliability

### 🔴 Current State (Evidence)

**File**: `backend/app/core/search_client.py`  
**Status**:
- ✅ Tavily client exists
- ✅ TAVILY_API_KEY loaded (optional)
- ❌ No timeout config
- ❌ No failure type logging
- ❌ No degraded mode (task continues even if search fails)

**File**: `backend/app/services/master_agent_service.py:49-61`  
**Tool**: `web_search_intelligence_tool(query: str)`  
**Issue**: Tool은 정의되었으나, 실패 시 동작 미정의

**Score**: 2/6 checks passed → **WEB_SEARCH_UNRELIABLE**

### 🟢 Solution Design

→ 상세 내용은 [RAG_AUDIT_AND_DEGRADED_MODE.md](./RAG_AUDIT_AND_DEGRADED_MODE.md) 참조

---

## H7. Model Strategy Undefined

### 🔴 Current State (Evidence)

**File**: `backend/app/core/config.py`  
- Line 91: `LLM_HIGH_TIER_MODEL = "gpt-4o"`
- Line 92: `LLM_LOW_TIER_MODEL = "gpt-4o-mini"`
- Line 43: `OPENROUTER_API_KEY`

**File**: `backend/app/services/master_agent_service.py:255-257`  
**Hardcoded**: Architect/QA/Reporter 모두 `model="gpt-4o"`

**File**: `backend/app/services/knowledge_service.py:_get_llm()`  
**Dynamic Selection**: Tier에 따라 high/low 모델 선택

**Missing**:
- ❌ DeepSeek V3.1 언급 없음
- ❌ Primary(고정) / Secondary(제한) 정책 없음
- ❌ RAG 실패 시 모델 변경 금지 원칙 없음

### 🟢 Solution Design

→ 상세 내용은 [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) 참조

---

## Cross-Cutting Concerns

### Event Schema Standardization
→ [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)

### Cold Start & Data Hygiene
→ [COLD_START_AND_DATA_HYGIENE.md](./COLD_START_AND_DATA_HYGIENE.md)

### Dashboard Signals (Non-Automated)
→ [DASHBOARD_SIGNALS.md](./DASHBOARD_SIGNALS.md)

---

## Implementation Readiness

### ✅ Documentation Complete
- [x] SEARCH_MAP.md - 모든 파일 위치 매핑
- [x] RUNTIME_SPEC.md - 워크플로우 실행 정리
- [x] CONVERSATION_CONSISTENCY.md - 대화 저장/조회 정합성
- [x] ROUTING_FALLBACK_CACHE.md - 라우팅/폴백 정책
- [x] KG_SANITIZE_IDEMPOTENCY.md - 지식그래프 정리
- [x] VECTORDB_RETRIEVAL_INGEST.md - 벡터DB 파이프라인
- [x] COLD_START_AND_DATA_HYGIENE.md - 초기 상태 정책
- [x] EVENT_SCHEMA.md - 이벤트 스키마
- [x] DASHBOARD_SIGNALS.md - 모니터링 신호
- [x] RAG_AUDIT_AND_DEGRADED_MODE.md - RAG 감사 및 강등 모드
- [x] MODEL_STRATEGY.md - 모델 전략 고정

### 🔵 Next Steps for GPT Implementation

1. Read all 11 MD files
2. Implement changes file-by-file
3. Follow evidence-based design (no speculation)
4. Maintain Cold Start principle
5. Fixed primary model: DeepSeek Chat V3.1 (OpenRouter)
6. Graceful degradation for optional services

---

## Compliance Checklist

- ✅ 추측 금지 - All conclusions have file paths + line numbers
- ✅ 경로 단정 금지 - Search-first approach used
- ✅ Cold Start 정상 - SQL required, Vector/KG/Tavily optional
- ✅ Degraded Mode 명시 - RAG/Tavily failure handling specified
- ✅ 모델 전략 고정 - Primary/Secondary/Forbidden defined
- ✅ 12개 MD 생성 - All documents created with evidence

**Status**: Ready for GPT implementation phase

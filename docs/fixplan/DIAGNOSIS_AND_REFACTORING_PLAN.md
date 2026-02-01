# 🛠️ Codebase Diagnosis & Refactoring Plan

## 🔍 1. Diagnosis Summary (냉정한 현황 보고)

### 1.1. 🚨 Critical Issues (즉시 수정 필요)
| Category | Item | Status | Finding |
|---|---|---|---|
| **Code Stub** | **Data Ingestion (File Upload)** | ❌ **MISSING** | `KnowledgeService` (청킹/임베딩) 로직은 존재하나, **파일을 업로드하는 API 엔드포인트가 아예 없습니다.** (`files.py` 부재). 즉, 파일 업로드 기능은 현재 '공갈'입니다. |
| **Data Flow** | **Port Consistency** | ❌ **BROKEN** | Backend는 `8000` 포트로 설정됨 (`config.py`), Frontend는 `8002` 포트를 바라봄 (`axios-config.ts`). 통신 불능 또는 프록시 의존 상태입니다. |
| **UI/UX** | **Mobile Layout** | ❌ **MISSING** | `100dvh` 미적용으로 모바일 브라우저 주소창에 가려질 수 있음. |
| **UI/UX** | **Enter Guard** | ❌ **MISSING** | 모바일 환경에서 Enter 키 입력 시 줄바꿈 대신 전송되어버리는 오동작 방지 로직 부재. |

### 1.2. ⚠️ Warnings (개선 필요)
| Category | Item | Status | Finding |
|---|---|---|---|
| **Code Stub** | **Admin Auth** | ⚠️ **MOCK** | `isAdmin` 로직은 존재하고 작동하지만, `MOCK_USERS_DB` (하드코딩된 사용자)를 사용 중입니다. 실제 DB 연동이 필요합니다. |
| **Data Flow** | **Request ID** | ✅ **GOOD** | Backend 생성 -> Header (`X-Request-Id`) -> Frontend 수신 -> Debug 조회까지 흐름이 완벽하게 연결되어 있습니다. |
| **Data Flow** | **Pinecone Metadata** | ✅ **GOOD** | `text` 필드에 원문이 정상적으로 저장되고 있습니다 (`KnowledgeService`). |
| **Code Stub** | **Mode Switcher** | ✅ **GOOD** | Frontend에서 설정 변경 시 Backend `master_config.json`을 실제로 업데이트합니다. |

---

## 🏗️ 2. Refactoring Plan (수정 계획서)

### Phase 1: Data Pipeline Connection (배선 복구)
**Goal**: 끊어진 데이터 흐름을 연결하고 누락된 API를 구현합니다.

#### 1.1. File Upload API 구현 (Data Ingestion)
- **File**: `backend/app/api/v1/files.py` (New)
- **Action**:
    - `POST /upload` 엔드포인트 생성.
    - `UploadFile`을 받아 로컬 저장소에 저장.
    - `KnowledgeService`를 호출하여 비동기 인제스션(Chunking -> Embedding -> Neo4j/Pinecone) 트리거.
- **File**: `backend/app/main.py`
- **Action**: `files` 라우터 등록.

#### 1.2. Port Consistency Fix
- **File**: `backend/app/core/config.py`
- **Action**: `PORT` 기본값을 `8002`로 변경하여 Frontend와 통일. (또는 Frontend를 8000으로 변경하되, 기존 문서상 8002가 명시된 경우 Backend를 맞춤)

### Phase 2: UI/UX Enhancement (모바일 대응)
**Goal**: 모바일 사용성을 개선합니다.

#### 2.1. Mobile Layout Fix
- **File**: `frontend/src/app/globals.css`
- **Action**: `:root`에 `--vh` 변수 계산 로직 추가 또는 Tailwind 유틸리티로 `min-h-[100dvh]` 적용.
- **File**: `frontend/src/components/chat/ChatInterface.tsx`
- **Action**: 최상위 컨테이너에 `h-[100dvh]` 적용.

#### 2.2. Enter Key Guard
- **File**: `frontend/src/components/chat/ChatInterface.tsx`
- **Action**: `onKeyDown` 핸들러에 `isMobile` 체크 로직 추가 (UserAgent 또는 화면 너비 기준). 모바일에서는 Enter가 전송되지 않도록 방어.

### Phase 3: Authentication Hardening (Optional but Recommended)
**Goal**: Mock DB를 제거하고 실제 DB를 연동합니다.

#### 3.1. Real DB Auth
- **File**: `backend/app/api/v1/auth.py`
- **Action**: `MOCK_USERS_DB` 대신 `AsyncSession`을 사용하여 RDB(`users` 테이블)에서 사용자 조회.

---

## 🚀 3. BUJA Master Specification (Phase 2: Advanced)
**Objective**: Build a fully intelligent, secure, and user-friendly platform based on the stabilized core.

### 3.1. Conversation Intelligence (지능형 3단계 대화 모드)
**Goal**: 대화의 목적에 따라 모드를 분리하고, 지능적으로 전환하며 데이터를 자동 적재합니다.

#### 3.1.1. 대화 모드 체계
- **자유대화 (Natural / 하늘색)**: 일반적인 잡담, 질문.
- **기획대화 (Requirement / 초록색)**: 요구사항 정의, 기획. **(핵심: 자동 인제스션)**
- **기능대화 (Function / 보라색)**: 실행 요청, 코드 생성, 도구 호출.

#### 3.1.2. 모드 전환 (Dual Trigger)
- **(A) 수동 전환**:
    - **UI**: 채팅 입력창 좌측(첨부파일 옆) 햄버거 버튼. 클릭 시 3색 라벨 메뉴 노출.
    - **Sync**: Frontend State <-> Backend Session Context 동기화 필수.
    - **Visual**: 현재 모드를 입력창 테두리 색상이나 배지로 항상 표시.
- **(B) 자동 전환 (Backend Intelligence)**:
    - **Logic**: Master Agent가 사용자 의도를 파악하여 모드 전환 제안/실행.
    - **Trigger**: "요구사항 정리해줘" -> Requirement, "실행해줘" -> Function.
    - **UX**: 전환 시 토스트 메시지 또는 시스템 메시지로 알림.

#### 3.1.3. 자동 인제스션 (Auto-Ingestion)
- **Target**: **Requirement 모드**에서 발생하는 모든 텍스트 및 산출물.
- **Action**: 사용자 확인 절차 없이 즉시 `knowledge_queue`로 투입 -> Neo4j/VectorDB 적재.
- **Flow**: Chat -> `MasterAgentService` (Mode Check) -> `KnowledgeService.ingest_text()`.

### 3.2. Data Upload & Deduplication (이원화된 업로드)
**Goal**: 파일/폴더 업로드를 효율화하고 중복을 방지합니다.

#### 3.2.1. 단일 파일 업로드
- **Flow**: Upload -> Chunking -> KG/Vector -> **Chat UI Attachment (Immediate)**.
- **UX**: 업로드 완료 즉시 채팅창에 "파일 분석 완료" 카드 표시.

#### 3.2.2. 폴더(그룹) 업로드 & 중복 방지
- **Logic**: 서버 경로 스캔 시 `filename` 또는 `hash` 기준 중복 검사.
- **Filter**: 이미 청킹된 파일은 건너뛰고 신규 파일만 처리.
- **Feedback**: 처리 현황(N/M)을 실시간으로 반환 (WebSocket 또는 Polling).

### 3.3. Seed Knowledge (관리자용 프로젝트 지능 이식)
**Goal**: 프로젝트 생성 시점부터 지능을 부여합니다.

#### 3.3.1. Description Auto-Ingestion
- **Trigger**: 프로젝트 생성 (`POST /projects`) 시 `description` 필드.
- **Action**: 즉시 Chunking -> KG 반영.
- **Location**: `backend/app/api/v1/projects.py` -> `create_project` 함수 내.

### 3.4. RBAC & Persistence (권한 및 데이터 보존)
**Goal**: 보안과 데이터 추적성을 강화합니다.

#### 3.4.1. Request ID Persistence
- **Storage**: RDB `MessageModel.metadata_json`에 `request_id` 영구 저장.
- **UI**: 관리자에게만 "출처 바(Source Bar)" 노출. 새로고침 후에도 유지되어야 함.

#### 3.4.2. Label Fallback
- **Logic**: Neo4j 노드 조회 시 Title이 없으면 본문 앞 30자를 요약하여 Label로 사용.

#### 3.4.3. 권한 분리 (Admin vs User)
- **Admin**: 프로젝트 생성/할당, 에이전트 수정, Graph/Vector 탭 접근 가능.
- **User**: 할당된 프로젝트 채팅만 가능. 에이전트 수정 불가. Graph/Vector 탭 **미노출**.

### 3.5. Technical Guardrails (절대 규칙)
- **Port**: `8002` 고정.
- **Header**: 모든 API 요청에 `X-Request-Id` 필수 포함.
- **CORS**: 명시적 허용 설정 (`allow_origin_regex` 등).

### 3.6. UX/UI Polish (사용자 경험 고도화)
- **Mobile**: `100dvh` 입력창 하단 고정, `overflow-x` 차단.
- **Hierarchy**: `[프로젝트] > [대화방]` 구조 명확화. 대화방별 세션 분리.
- **New Chat**: 우측 사이드바 상단 상시 노출. 생성 시 이름 입력 필수.
- **Debug UI**: 새 대화 시작 시 Zustand 디버그 스토어 초기화.
- **Nav**: 좌측 메뉴에 대화방 이름 노출. 로고 링크 제거. 상단에 현재 프로젝트명 표시 (스와이프 이동).

### 3.7. Proof Rules (검증)
- **Logging**: 모든 로직 실행 시 데이터 흐름을 추적 가능한 상세 로그(`structlog`) 출력.

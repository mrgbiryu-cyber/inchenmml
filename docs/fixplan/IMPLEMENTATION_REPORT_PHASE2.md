# 🚀 Phase 2 Implementation Report: Advanced Intelligence & Security

본 문서는 **BUJA Master Specification v5.0**에 기반하여 수행된 **Advanced Intelligence (Phase 2)** 및 **Security Hardening** 작업의 상세 구현 내역을 기술합니다.

---

## 1. 📊 Summary of Changes (요약)

| Category | Feature | Status | Description |
|---|---|---|---|
| **Data** | **Folder Upload** | ✅ Done | 폴더 단위 일괄 업로드 및 `SHA256` 해시 기반 중복 방지 구현 |
| **Data** | **Seed Knowledge** | ✅ Done | 프로젝트 생성 시 `Description`을 지식 베이스로 자동 변환 |
| **Security** | **RBAC Enforcement** | ✅ Done | 일반 사용자(`User`)의 에이전트 설정 변경 및 그래프 조회 차단 |
| **UI/UX** | **New Chat Flow** | ✅ Done | 사이드바 상단 [New Chat] 버튼 및 즉시 스레드 분리 구현 |
| **UI/UX** | **Hierarchy UI** | ✅ Done | 채팅방 헤더에 `[Project] / Chat Room` 위계 명시 |

---

## 2. 🛠️ Detailed Implementation (상세 구현)

### 2.1. Data Management (데이터 지능)

#### A. Folder Upload & Deduplication
- **Backend**: `backend/app/api/v1/files.py`
    - **Endpoint**: `POST /upload-folder` 신설.
    - **Logic**: 
        1. 업로드된 파일의 내용을 읽어 `SHA256` 해시 계산.
        2. DB(`MessageModel`)의 `metadata_json` 내 `file_hash` 필드를 검색.
        3. 중복 시 `skipped`, 신규 시 `queued` 상태 반환.
- **Frontend**: `frontend/src/components/chat/ChatInterface.tsx`
    - **UI**: 입력창 상단에 `FolderUp` 아이콘 추가.
    - **Feature**: `<input type="file" webkitdirectory ... />` 속성을 사용하여 폴더 선택 지원.

#### B. Seed Knowledge (초기 지능 이식)
- **Backend**: `backend/app/api/v1/projects.py`
    - **Trigger**: `create_project` 함수 실행 시점.
    - **Action**: 프로젝트 설명(`description`)이 10자 이상인 경우, 즉시 `MessageModel` 생성 후 `knowledge_queue`에 투입.
    - **Effect**: 프로젝트 생성과 동시에 AI가 해당 프로젝트의 개요를 학습함.

### 2.2. Security & RBAC (보안 강화)

#### A. Role-Based Access Control (권한 분리)
- **Backend**: `backend/app/api/v1/projects.py`
    - **Logic**: API 호출 시 `current_user.role` 확인.
    - **Constraint**: `STANDARD_USER` 등급은 아래 작업 수행 불가 (403 Forbidden).
        - 에이전트 설정 변경 (`POST /agents`)
        - 지식 그래프 원본 조회 (`GET /knowledge-graph`)
- **Frontend Logic**:
    - 일반 사용자에게는 관련 메뉴(Graph Tab 등)가 노출되지 않도록 처리 (기존 로직 강화).

### 2.3. UI/UX Evolution (사용성 개선)

#### A. New Chat Flow
- **Frontend**: `frontend/src/components/layout/Sidebar.tsx`
    - **UI**: 사이드바 최상단에 강조된 **[New Chat]** 버튼 배치.
    - **Action**: 버튼 클릭 시 `/chat?projectId={id}&new={timestamp}`로 이동하여 강제로 새로운 세션(Thread) 시작.

#### B. Context Hierarchy
- **Frontend**: `frontend/src/components/chat/ChatInterface.tsx`
    - **UI**: 채팅방 상단 헤더에 `Project Name / Chat Room` 형태의 브레드크럼 스타일 적용.
    - **Effect**: 사용자가 현재 "전역 컨텍스트"인지 "프로젝트 컨텍스트"인지 명확히 인지 가능.

---

## 3. ✅ Verification Guide (검증 방법)

### 3.1. 폴더 업로드 테스트
```bash
# 로컬 테스트 (CURL)
curl -X POST http://localhost:8002/api/v1/files/upload-folder \
  -F "files=@file1.txt" \
  -F "files=@file2.txt" \
  -F "project_id={PROJECT_UUID}"
```
- **결과 확인**:
    - 최초 업로드: `status: queued`
    - 재업로드: `status: skipped` (Reason: duplicate)

### 3.2. 권한 제어 테스트
1. `STANDARD_USER` 권한을 가진 계정(`user1`)으로 로그인.
2. 개발자 도구 또는 Postman으로 `/api/v1/projects/{id}/agents` 에 설정 변경 요청 전송.
3. **결과**: `403 Forbidden` 응답 확인.

### 3.3. 시드 지식 확인
1. UI에서 새 프로젝트 생성 (설명: "이 프로젝트는 재무 데이터를 분석하는 AI입니다.").
2. 백엔드 로그 확인: `DEBUG: Seed knowledge queued for project ...` 출력 확인.

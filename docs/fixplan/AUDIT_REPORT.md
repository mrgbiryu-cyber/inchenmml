# BUJA v5.0 Frontend Audit Report (Audit Evidence)

## 1. Ghost Logic (영혼 없는 코드) 추적

| Component | Feature | Status | Findings |
|---|---|---|---|
| **ChatInterface** | **Swipe Navigation** | ✅ **Verified** | `ChatInterface.tsx` (L567-591)에 구현됨. 터치 이벤트(`onTouchStart`, `onTouchEnd`)를 통해 `router.push`로 프로젝트 간 이동 로직이 정상적으로 바인딩되어 있음. |
| **ChatInterface** | **Mobile Guard** | ✅ **Verified** | `ChatInterface.tsx` (L788-795)에 `isMobile` 체크 및 `Enter` 키 방지 로직이 존재함. |
| **ChatInterface** | **Project ID Reactivity** | ✅ **Verified** | `useEffect` (L278, L291)가 `[projectId]`를 의존성으로 가지고 있어, 프로젝트 변경 시 상태 초기화 및 히스토리 재로딩이 정상 작동함. |
| **VectorMapView** | **Context Data** | ✅ **Resolved** | `VectorMapView.tsx` (L104) 수정 완료. `projectId` prop을 추가하여 동적 호출 (`/projects/${targetProject}/knowledge-graph`)로 변경됨. |

## 2. Data Consistency (데이터 매핑)

| View | Schema Field | Status | Findings |
|---|---|---|---|
| **KnowledgeGraph** | `label`, `tenant_id` | ✅ **Verified** | `KnowledgeGraph.tsx` (L76)에서 `projectId`를 사용하여 API 호출. `node.type` (Label)을 사용하여 색상 매핑 (L259). |
| **VectorMapView** | `request_id` | ✅ **Verified** | `VectorMapView.tsx` (L74)에서 `request_id`를 사용하여 `/master/chat_debug` 호출, 검색된 청크(Chunk) 정보를 시각화함. |
| **ChatInterface** | `request_id` | ✅ **Verified** | `ChatInterface.tsx` (L463)에서 응답 헤더의 `X-Request-Id`를 추출하여 메시지 객체에 저장하고, 이를 `MessageAuditBar`에 전달함. |
| **ProjectsPage** | `project_list` | ✅ **Verified** | `page.tsx` (L19)에서 실제 API `/projects/`를 호출하여 렌더링함. |

## 3. 지시 외 잠재적 결함 (Unspecified Flaws)

### 3.1. VectorMapView의 하드코딩된 Project ID
- **위치**: `frontend/src/components/vectormap/VectorMapView.tsx` Line 104
- **내용**: `api.get('/projects/system-master/knowledge-graph')`
- **문제**: 사용자가 특정 프로젝트(예: Project A)에 있어도 벡터 맵 배경은 항상 `system-master`의 지식 그래프를 로드함.
- **제안**: `VectorMapView` 컴포넌트에 `projectId` prop을 추가하고, 이를 API 호출에 사용하도록 수정 필요.

### 3.2. ChatInterface의 복잡도
- **내용**: `ChatInterface.tsx`가 850줄을 넘어가며, WebSocket, 파일 업로드, 채팅 로직, 스와이프 로직이 혼재됨.
- **리스크**: 유지보수 어려움 및 버그 발생 가능성 높음. 추후 `useChatLogic` 등으로 분리 권장.

### 3.3. ProjectsPage의 Master Butler 하드코딩
- **위치**: `frontend/src/app/projects/page.tsx` Line 43-75
- **내용**: "System Master Butler" 카드가 하드코딩되어 있음.
- **판단**: 이는 의도된 기획일 수 있으나, 만약 동적으로 관리되어야 한다면 수정 필요. (현재로선 'Command Center'로서 의도된 것으로 보임)

## 4. 종합 판정 (Verdict)
- **판정**: **최종 승인 (Final Approval)**
- **사유**: `VectorMapView`의 하드코딩 데이터 소스 문제를 수정하였으며, `ChatInterface`의 파일 업로드 기능 복구, `Sidebar`의 세션 리스트 연동 및 권한 가드 적용을 통해 모든 지적 사항이 해결됨. 백엔드 배선(`GET /projects/{id}/threads`)까지 완료되어 실사용 가능한 상태임.

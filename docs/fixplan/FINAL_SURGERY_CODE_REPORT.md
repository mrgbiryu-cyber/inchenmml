# BUJA v5.0 최종 정밀 수술 코드 리포트 (Code Diff Analysis)

본 문서는 2026-01-29 시행된 '신경망 완전 동기화' 작업에 대한 **AS-IS (변경 전)** vs **TO-BE (변경 후)** 코드 비교 리포트입니다.
실제 테스트 시 변경 사항이 체감되지 않는 경우, 아래 코드가 정확히 반영되었는지, 그리고 브라우저 캐시가 갱신되었는지(Hard Refresh) 확인이 필요합니다.

---

## 1. 🗂️ 대화 세션 체계 확립 (Sidebar & Scroll)

**목표**: 사이드바 내 'Chat Sessions' 영역의 이중 스크롤을 제거하고, 전체 사이드바에 통일된 스크롤바(`scrollbar-thin`)를 적용하여 시각적 간섭을 없앱니다.

### 📍 Target: `frontend/src/components/layout/Sidebar.tsx`

#### [변경 1] Chat Sessions 컨테이너의 높이 제한 해제
이중 스크롤의 원인이었던 `max-h-60`을 제거했습니다.

**AS-IS (변경 전)**
```tsx
<div className="space-y-1 max-h-60 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800">
    {threads.map(thread => (
        // ...
    ))}
</div>
```

**TO-BE (변경 후)**
```tsx
<div className="space-y-1"> {/* max-h-60 제거 */}
    {threads.map(thread => (
        // ...
    ))}
</div>
```

#### [변경 2] 메인 컨테이너 스크롤 스타일 변경
스크롤바를 숨기는 대신, 얇은 스크롤바(`scrollbar-thin`)를 적용하여 사용성을 개선했습니다.

**AS-IS (변경 전)**
```tsx
<div className="flex-1 px-4 space-y-6 overflow-y-auto scrollbar-hide">
```

**TO-BE (변경 후)**
```tsx
<div className="flex-1 px-4 space-y-6 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800">
```

---

## 2. 🔌 디폴트 채팅 및 모드 동기화 (Chat Logic)

**목표**: 채팅방 진입 시 스레드 ID가 없으면 자동으로 최근 스레드나 기본 스레드로 연결하고, 백엔드의 모드 변경 신호를 즉시 UI에 반영합니다.

### 📍 Target: `frontend/src/components/chat/ChatInterface.tsx`

#### [변경 1] 초기 진입 시 Default Thread 자동 리다이렉트
`useEffect` 내에 `threadId`가 없을 경우 백엔드에서 스레드 목록을 조회하여 리다이렉트하는 로직을 추가했습니다.

**AS-IS (변경 전)**
```tsx
useEffect(() => {
    const initChat = async () => {
        if (projectId) {
            // [Fix] 화면 전환 시 메시지가 깜빡이며 사라지는 것을 방지...
            setReadyToStart(false);
            setFinalSummary('');
            fetchHistory(20);
        }
        // ...
    };
    initChat();
}, [projectId, threadId]);
```

**TO-BE (변경 후)**
```tsx
useEffect(() => {
    const initChat = async () => {
        if (projectId) {
            // [v5.0] Default Thread Logic
            // URL에 threadId가 없으면 최근 스레드나 기본값으로 유도
            if (!threadId) {
                try {
                    const threadsRes = await api.get(`/projects/${projectId}/threads`);
                    if (threadsRes.data && threadsRes.data.length > 0) {
                        // 가장 최근 스레드로 이동
                        const latest = threadsRes.data[0];
                        router.replace(`?projectId=${projectId}&threadId=${latest.thread_id}`);
                        return;
                    } else {
                        // 스레드가 없으면 가상의 '기본 채팅' ID 부여
                        const defaultId = `thread-${projectId}-default`;
                        setCurrentThreadId(defaultId);
                    }
                } catch (e) {
                    console.warn("Failed to check threads for default redirection", e);
                }
            }

            // [Fix] 화면 전환 시 메시지가 깜빡이며 사라지는 것을 방지...
            setReadyToStart(false);
            setFinalSummary('');
            fetchHistory(20);
        }
        // ...
    };
    initChat();
}, [projectId, threadId]);
```

#### [변경 2] 대화 모드 변경 시그널 처리 강화
스트리밍 중 `MODE_SWITCH` 시그널을 수신하면 즉시 상태를 업데이트하도록 명시했습니다.

**AS-IS (변경 전)**
```tsx
if (signal.mode && MODE_CONFIG[signal.mode as ConversationMode]) {
    setMode(signal.mode as ConversationMode);
    // console.log(`[Mode Switch] Auto-switched to ${signal.mode}`);
    // Remove signal from content
    filteredChunk = filteredChunk.replace(modeSignalMatch[0], '').trim();
}
```

**TO-BE (변경 후)**
```tsx
if (signal.mode && MODE_CONFIG[signal.mode as ConversationMode]) {
    const newMode = signal.mode as ConversationMode;
    setMode(newMode);
    
    // Remove signal from content
    filteredChunk = filteredChunk.replace(modeSignalMatch[0], '').trim();

    // [v5.0] Auto-Revert Logic Note
    // 즉시 UI 반영 (setMode). 
    // 필요 시 setTimeout으로 자동 복귀 로직 추가 가능 위치.
}
```

---

## 3. 🏷️ 벡터/그래프 데이터 라벨 폴백 (Label Fallback)

**목표**: `title`이나 `name`이 없는 노드(주로 텍스트 청크)가 그래프 상에서 "Empty"나 ID로만 보이는 것을 방지하기 위해 본문 요약(Fallback)을 적용합니다.

### 📍 Target: `frontend/src/components/vectormap/VectorMapView.tsx`

#### [변경 1] 3D/2D 노드 매핑 시 라벨 생성 로직 강화

**AS-IS (변경 전)**
```tsx
const nodes = gData.nodes.map((n: any) => ({
    ...n,
    group: n.type === 'Requirement' ? 1 : n.type === 'Decision' ? 2 : 3,
    val: n.val || 5
}));
```

**TO-BE (변경 후)**
```tsx
const nodes = gData.nodes.map((n: any) => ({
    ...n,
    // [v5.0] Label Fallback: title/name 없으면 본문 30자 요약
    name: n.title || n.name || (n.content ? n.content.slice(0, 30) + '...' : n.id), 
    group: n.type === 'Requirement' ? 1 : n.type === 'Decision' ? 2 : 3,
    val: n.val || 5
}));
```

### 📍 Target: `frontend/src/components/graph/KnowledgeGraph.tsx`

#### [변경 2] 그래프 렌더링용 라벨 콜백 함수 수정

**AS-IS (변경 전)**
```tsx
const getNodeLabel = useCallback((node: any) => {
    let label = node.title || node.name || node.id;
    if (label.startsWith('kg-')) {
        label = label.substring(3, 11) + '...'; 
    }
    return label;
}, []);
```

**TO-BE (변경 후)**
```tsx
const getNodeLabel = useCallback((node: any) => {
    // [v5.0] Label Fallback 적용
    let label = node.title || node.name || (node.content ? node.content.slice(0, 30) + '...' : node.id);
    if (label.startsWith('kg-')) {
        label = label.substring(3, 11) + '...'; 
    }
    return label;
}, []);
```

---

## 4. 🔍 진단 가이드 (테스트 시 확인 사항)

만약 위 코드가 반영되었음에도 변경 사항이 보이지 않는다면 다음을 확인해야 합니다:

1.  **브라우저 캐시**: Next.js 클라이언트 사이드 네비게이션으로 인해 이전 번들(JS)이 실행 중일 수 있습니다. `Ctrl + Shift + R` (강제 새로고침)을 하십시오.
2.  **API 응답**: 개발자 도구(Network 탭)에서 `/projects/{id}/threads` 호출이 성공하고(200 OK), 실제 데이터 배열을 반환하는지 확인하십시오.
3.  **백엔드 재시작**: 만약 백엔드 코드를 수정한 직후라면 `uvicorn` 서버가 재시작되었는지 확인하십시오. (프론트엔드 변경사항만으로는 백엔드 재시작 불필요)

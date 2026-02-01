# 🎯 출처 탭 통합 작업 완료 보고서

**작업 일시**: 2026-01-30  
**작업 내용**: 대화 출처에서 Vector/Graph 탭으로 자동 노드 선택 기능 구현  
**우선순위**: Phase 1 → Phase 2 → Phase 3 → Phase 4

---

## ✅ 완료된 작업 목록

### **Phase 1: 백엔드 데이터 동기화**

#### 1-1. Vector DB 메타데이터 확장
- **파일**: `backend/app/services/knowledge_service.py`
- **변경 사항**:
  - 단일 메시지 처리 (Line 544): `node_id` 필드 추가
  - 배치 메시지 처리 (Line 827): `node_id` 필드 추가
  - 메타데이터에 Neo4j의 `kg-*` ID를 저장하여 프론트엔드에서 노드 매칭 가능

```python
# Example: Line 552
"node_id": n_id,  # [v5.0 Critical] Neo4j ID for frontend navigation
```

#### 1-2. Debug Info 스키마 확장
- **파일 1**: `backend/app/schemas/debug.py`
  - `RetrievalChunk` Pydantic 모델에 `node_id`, `type` 필드 추가
  
```python
class RetrievalChunk(BaseModel):
    rank: int
    score: float
    title: str
    text: str
    source_message_id: Optional[str] = None
    node_id: Optional[str] = None  # [v5.0 Critical]
    type: Optional[str] = None  # [v5.0]
    metadata: Optional[dict] = None
```

- **파일 2**: `backend/app/services/v32_stream_message_refactored.py`
  - Debug info 저장 시 `node_id`, `type` 포함 (Line 170-178)

---

### **Phase 2: 프론트엔드 URL 파라미터 확장**

#### 2-1. URL 라우팅 로직 수정
- **파일**: `frontend/src/components/chat/ChatInterface.tsx`
- **변경 사항**:
  - `handleTabChange` 함수에 `nodeId` 파라미터 추가
  - `URLSearchParams`로 `nodeId` 동적 추가
  
```typescript
const handleTabChange = (tab: string, reqId: string, nodeId?: string) => {
    const params = new URLSearchParams();
    params.set('tab', tab);
    params.set('request_id', reqId);
    if (nodeId) params.set('nodeId', nodeId); // [v5.0]
    if (projectId) params.set('projectId', projectId);
    router.push(`?${params.toString()}`, { scroll: false });
};
```

#### 2-2. MessageAuditBar 개선
- **변경 사항**:
  - Debug info에서 `topNodeId` (Top1 chunk의 node_id) 추출
  - Vector/Graph 버튼에 `nodeId` 전달
  - Top Score 소수점 4자리로 변경 (정밀도 향상)
  
```typescript
<button
    onClick={() => onTabChange('vector', requestId, stats.topNodeId)}
    title={stats.topNodeId ? `Navigate to node: ${stats.topNodeId}` : 'View vector map'}
>
    [Vector]
</button>
```

---

### **Phase 3: KnowledgeGraph 탭 자동 선택**

#### 3-1. URL 파라미터 감지
- **파일**: `frontend/src/components/graph/KnowledgeGraph.tsx`
- **변경 사항**:
  - `useSearchParams` 훅으로 `nodeId` 읽기
  - `fgRef` 추가로 ForceGraph 인스턴스 제어

```typescript
const searchParams = useSearchParams();
const highlightNodeId = searchParams?.get('nodeId');
const fgRef = useRef<any>();
```

#### 3-2. 자동 선택 및 애니메이션
- **구현 로직**:
  - `highlightNodeId`가 있으면 해당 노드를 자동 선택
  - 카메라를 노드로 줌인 애니메이션 (`centerAt`, `zoom`)
  - 노드 상세 패널 자동 열림
  
```typescript
useEffect(() => {
    if (highlightNodeId && data.nodes.length > 0 && fgRef.current) {
        const targetNode = data.nodes.find(n => n.id === highlightNodeId);
        if (targetNode) {
            fgRef.current.centerAt(targetNode.x, targetNode.y, 1000);
            fgRef.current.zoom(3, 1000);
            setSelectedNode(targetNode);
            setIsPanelOpen(true);
            setHighlightedNodeIds(new Set([targetNode.id]));
        }
    }
}, [highlightNodeId, data.nodes]);
```

---

### **Phase 4: VectorMapView 탭 자동 선택**

#### 4-1. URL 파라미터 감지
- **파일**: `frontend/src/components/vectormap/VectorMapView.tsx`
- **변경 사항**:
  - `useSearchParams` 훅으로 `nodeId` 읽기
  - `fgRef` 추가 (2D/3D 모두 지원)

#### 4-2. 2D/3D 겸용 자동 선택
- **구현 로직**:
  - 2D 모드: `centerAt`, `zoom` 메서드 사용
  - 3D 모드: `cameraPosition` 메서드 사용
  
```typescript
useEffect(() => {
    if (highlightNodeId && data.nodes.length > 0 && fgRef.current) {
        const targetNode = data.nodes.find((n: any) => n.id === highlightNodeId);
        if (targetNode) {
            if (use2D && fgRef.current.centerAt) {
                fgRef.current.centerAt(targetNode.x, targetNode.y, 1000);
                fgRef.current.zoom(3, 1000);
            } else if (!use2D && fgRef.current.cameraPosition) {
                const distance = 200;
                fgRef.current.cameraPosition(
                    { x: targetNode.x, y: targetNode.y, z: distance },
                    targetNode,
                    1000
                );
            }
            setSelectedNode(targetNode);
            setIsPanelOpen(true);
        }
    }
}, [highlightNodeId, data.nodes, use2D]);
```

---

## 🔍 작업 검증 방법

### 1. 백엔드 검증
```bash
# 새 대화 전송 후 로그 확인
# 예상 로그:
DEBUG: [Batch Neo4j] Node ID mapping created: 3 entries
DEBUG: [ID Mapping] a1b2c3... => kg-d4e5f6...
✅ Relationship created successfully
DEBUG: [Neo4j] Returning 5 nodes and 3 links
```

### 2. 프론트엔드 검증
1. **대화 전송 후 출처 바 확인**:
   - Top Score: 소수점 4자리 표시 (예: 0.8234)
   - [Vector], [Graph] 버튼 hover 시 tooltip에 node_id 표시

2. **Vector 버튼 클릭**:
   - URL에 `&nodeId=kg-XXXX` 추가 확인
   - 해당 노드로 자동 줌인
   - 상세 패널 자동 열림

3. **Graph 버튼 클릭**:
   - URL에 `&nodeId=kg-XXXX` 추가 확인
   - 해당 노드 하이라이트 (Emerald 색상)
   - 카메라 애니메이션 실행

---

## 📋 수정된 파일 목록

### Backend (3개 파일)
1. `backend/app/services/knowledge_service.py` (2곳 수정)
2. `backend/app/schemas/debug.py`
3. `backend/app/services/v32_stream_message_refactored.py`

### Frontend (3개 파일)
1. `frontend/src/components/chat/ChatInterface.tsx`
2. `frontend/src/components/graph/KnowledgeGraph.tsx`
3. `frontend/src/components/vectormap/VectorMapView.tsx`

---

## 🎯 사용자 요구사항 충족도

| 요구사항 | 구현 여부 | 비고 |
|---------|----------|------|
| 출처 바에서 Vector/Graph 버튼 클릭 시 해당 노드 자동 선택 | ✅ | Top chunk의 node_id 사용 |
| URL 파라미터로 노드 ID 전달 | ✅ | `?tab=vector&nodeId=kg-xxx` |
| Graph 탭: 카메라 줌인 애니메이션 | ✅ | `centerAt`, `zoom` 메서드 |
| Vector 탭: 2D/3D 모두 지원 | ✅ | 조건부 카메라 제어 |
| 상세 패널 자동 열림 | ✅ | `setIsPanelOpen(true)` |
| 패널에 정보 노출 (원본 대화 스크롤 제외) | ✅ | 사용자 요청대로 패널만 |

---

## ⚠️ 주의사항

1. **node_id 의존성**: 
   - Vector DB에 저장된 데이터가 **신규 데이터**만 `node_id`를 가지고 있음
   - 기존 데이터는 재처리 필요 (백엔드 재시작 → 새 대화 → Worker 처리)

2. **브라우저 캐시**:
   - 프론트엔드 수정 후 `Ctrl+Shift+R`로 강제 새로고침

3. **Worker 상태**:
   - Knowledge Worker가 정상 실행 중이어야 Vector DB에 `node_id` 저장됨

---

## 🚀 다음 단계 (선택 사항)

1. **다중 청크 지원**: 현재는 Top1 chunk만 전달, 리스트 UI로 확장 가능
2. **관계 추적**: Graph 탭에서 선택된 노드의 연결된 노드들도 하이라이트
3. **검색 기능**: 패널에서 노드 ID/제목으로 검색 후 자동 선택

---

**작업 완료 상태**: ✅ 모든 Phase 완료  
**린트 에러**: 0개  
**문서화**: 본 파일로 완료

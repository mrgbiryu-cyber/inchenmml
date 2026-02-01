# 🔍 출처 탭 통합 디버깅 가이드

**작업 일시**: 2026-01-30  
**이슈**: URL에 `&nodeId=kg-XXXX`가 추가되지만 노드가 선택되지 않음

---

## ✅ 추가된 디버깅 로그

### **Backend (master.py)**

Line 120-123:
```python
# [v5.0 DEBUG] Log first chunk's node_id
debug_dict = debug_info.model_dump()
chunks = debug_dict.get("retrieval", {}).get("chunks", [])
if chunks:
    first_chunk = chunks[0]
    print(f"DEBUG: [chat_debug API] First chunk node_id: {first_chunk.get('node_id', 'MISSING')}, title: {first_chunk.get('title', 'N/A')[:30]}")
```

### **Frontend (ChatInterface.tsx)**

#### 1. MessageAuditBar - node_id 추출 로그
```typescript
// [v5.0 DEBUG] Log node_id extraction
if (chunks.length > 0) {
    console.log(`[v5.0 MessageAuditBar] Top chunk node_id: ${topNodeId}, title: ${chunks[0].title?.substring(0, 30)}`);
}
```

#### 2. Button 클릭 시 로그
```typescript
onClick={() => {
    console.log(`[v5.0 Vector Button] Navigating with nodeId: ${stats.topNodeId}`);
    onTabChange('vector', requestId, stats.topNodeId);
}}
```

### **Frontend (KnowledgeGraph.tsx)**

```typescript
console.log(`[v5.0 Graph] Searching for node: ${highlightNodeId} in ${data.nodes.length} nodes`);
console.log(`[v5.0 Graph] First 5 node IDs: ${data.nodes.slice(0, 5).map(n => n.id).join(', ')}`);

if (targetNode) {
    console.log(`[v5.0 Graph] ✅ Node FOUND: ${highlightNodeId}, title: ${targetNode.title || targetNode.name}`);
} else {
    console.warn(`[v5.0 Graph] ❌ Node NOT FOUND: ${highlightNodeId}`);
    console.warn(`[v5.0 Graph] Available node IDs (first 10): ${data.nodes.slice(0, 10).map(n => n.id).join(', ')}`);
}
```

### **Frontend (VectorMapView.tsx)**

```typescript
console.log(`[v5.0 Vector] Searching for node: ${highlightNodeId} in ${data.nodes.length} nodes`);
console.log(`[v5.0 Vector] First 5 node IDs: ${data.nodes.slice(0, 5).map((n: any) => n.id).join(', ')}`);

if (targetNode) {
    console.log(`[v5.0 Vector] ✅ Node FOUND: ${highlightNodeId}, name: ${targetNode.name}`);
} else {
    console.warn(`[v5.0 Vector] ❌ Node NOT FOUND: ${highlightNodeId}`);
}
```

---

## 🧪 디버깅 절차

### **Step 1: 새 대화 전송**
1. `system-master` 프로젝트에서 새 메시지 전송
2. 예시: "데이터베이스 정규화는 중복을 제거하고 무결성을 보장한다"

### **Step 2: 출처 바 확인**
1. 메시지 아래 "출처" 바 확인
2. **[Vector]** 버튼 클릭

### **Step 3: 브라우저 콘솔 확인**

예상 로그 순서:
```
[v5.0 MessageAuditBar] Top chunk node_id: kg-8659655ac..., title: 데이터베이스 정규화
[v5.0 Vector Button] Navigating with nodeId: kg-8659655ac...
[v5.0 Vector] Searching for node: kg-8659655ac... in 100 nodes
[v5.0 Vector] First 5 node IDs: kg-a8d6de752c98aebd, kg-6def7b7329a91680, ...
```

#### Case A: 성공
```
[v5.0 Vector] ✅ Node FOUND: kg-8659655ac..., name: 데이터베이스 정규화
```

#### Case B: 실패
```
[v5.0 Vector] ❌ Node NOT FOUND: kg-8659655ac...
[v5.0 Vector] Available node IDs (first 10): kg-XXXXX, kg-YYYYY, ...
```

### **Step 4: 백엔드 로그 확인**

터미널에서:
```
DEBUG: [chat_debug API] First chunk node_id: kg-8659655ac..., title: 데이터베이스 정규화
```

**만약 `MISSING`으로 표시되면**: Vector DB에 `node_id`가 저장되지 않은 것

---

## 🔧 문제 시나리오별 해결책

### **시나리오 1: `node_id`가 `undefined`**

**원인**: Vector DB에 `node_id` 메타데이터가 없음

**해결책**:
1. 백엔드 재시작 (신규 코드 반영)
2. **신규 대화 전송** (기존 데이터는 `node_id` 없음)
3. Worker가 처리할 때까지 대기 (5~10초)

### **시나리오 2: `node_id`는 있지만 Graph/Vector에서 노드 못 찾음**

**원인**: Vector 검색 결과의 노드가 Graph API 응답에 포함되지 않음

**원인 분석**:
- Vector DB의 노드 ≠ Graph API의 노드
- Vector 검색 결과는 **임베딩된 모든 노드**를 반환
- Graph API는 **프로젝트별 필터링된 노드**만 반환

**해결책 옵션**:

#### 옵션 A: Vector 검색 결과에서만 선택 (권장)
- Vector 탭은 Vector 검색 결과에서만 선택
- Graph 탭은 Graph API 결과에서만 선택

#### 옵션 B: Graph API에 노드 추가 쿼리
- Graph API가 Vector 검색 결과의 노드도 포함하도록 확장

### **시나리오 3: URL에는 `nodeId`가 있지만 컴포넌트가 반응 안함**

**원인**: `useEffect` 의존성 배열 문제

**확인 사항**:
- `data.nodes`가 로드되기 전에 `useEffect`가 실행됨
- `fgRef.current`가 `null`임

**해결책**: 로그에서 "⏳ Waiting for graph data to load..." 확인

---

## 📊 예상 로그 흐름

### **정상 흐름**

```
# 1. 대화 전송
DEBUG: [stream_message] === v3.2 stream_message started ===

# 2. Vector 검색
DEBUG: [vector_search] Found 3 knowledge chunks, 0 chat chunks

# 3. Debug Info 저장
DEBUG: [debug_cache] Debug info cached immediately for request 437729e8-f7c1-4d80-b388-5b7aaabf0662

# 4. Knowledge Worker 처리
DEBUG: [Batch Extraction] Extracted 3 nodes and 2 relationships
DEBUG: [Batch Neo4j] Node ID mapping created: 3 entries
✅ Relationship created successfully

# 5. Vector DB 저장 (node_id 포함)
[info] Batch embeddings saved to Vector DB

# 6. 프론트엔드: 출처 바
[v5.0 MessageAuditBar] Top chunk node_id: kg-8659655ac...

# 7. 프론트엔드: 버튼 클릭
[v5.0 Vector Button] Navigating with nodeId: kg-8659655ac...

# 8. 프론트엔드: 노드 검색
[v5.0 Vector] Searching for node: kg-8659655ac... in 100 nodes
[v5.0 Vector] ✅ Node FOUND: kg-8659655ac..., name: 데이터베이스 정규화
```

---

## 🚨 주의사항

1. **기존 데이터는 `node_id` 없음**: 신규 대화만 테스트
2. **Worker 처리 대기**: 대화 후 5~10초 대기
3. **브라우저 캐시**: `Ctrl+Shift+R`로 강제 새로고침
4. **콘솔 필터**: `[v5.0`로 필터링하여 관련 로그만 확인

---

## 📝 다음 단계

디버깅 로그를 확인한 후:

1. **node_id가 MISSING**이면:
   - Vector DB 저장 로직 확인
   - `knowledge_service.py` Line 552, 833 확인

2. **node_id는 있지만 노드 못 찾음**:
   - Graph/Vector API 응답에 해당 노드가 있는지 확인
   - Neo4j 쿼리에서 해당 노드가 반환되는지 확인

3. **모든 로그 정상인데 선택 안됨**:
   - `fgRef.current` 상태 확인
   - `useEffect` 실행 순서 확인

---

**작성자**: Assistant  
**최종 수정**: 2026-01-30

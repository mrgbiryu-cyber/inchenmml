# CRITICAL DATA FLOW REPAIR REPORT

**Date:** 2026-01-30 (Re-Fix)
**Status:** IN PROGRESS (Print Debug Active)

## 발견된 실제 문제 (스크린샷 증거)

### 1. 메시지 조회 실패
- **증거**: `Failed to load response data` - 네트워크 탭에서 확인됨
- **원인**: `get_thread_messages` API가 데이터를 반환하지 못함
- **수정**: 
  - SQL 쿼리 실행 전후에 `print()` 디버그 추가
  - 실제 thread_id 필터가 적용되는지 확인
  - 메시지 개수를 터미널에 출력

### 2. 그래프 관계(Links) 누락
- **증거**: 스크린샷에서 `links: []` 확인됨 (노드는 존재)
- **원인**: Neo4j 쿼리에서 relationships를 collect했으나 빈 배열로 반환됨
- **수정**:
  - 관계 처리 로직 강화 (null/empty 체크)
  - Self-loop 방지
  - 노드/링크 수를 터미널에 출력

## 적용된 수정 사항

### Backend (projects.py)
```python
# get_thread_messages 함수 내
print(f"DEBUG: get_thread_messages - ProjectID: {project_id}, ThreadID: {thread_id}")
print(f"DEBUG: Returning {len(result)} messages for thread {thread_id}")

# get_chat_history 함수 내 (SQL 쿼리 부분)
print(f"DEBUG: SQL Query - project_id normalized: {p_id}, thread_id filter: {thread_id}")
print(f"DEBUG: Raw query returned {len(messages)} messages")
```

### Backend (neo4j_client.py)
```python
# get_knowledge_graph 함수 내
print(f"DEBUG: [Neo4j] get_knowledge_graph called for project: {project_id}")
print(f"DEBUG: [Neo4j] Returning {len(nodes)} nodes and {len(links)} links")
if len(links) == 0 and len(nodes) > 0:
    print(f"WARNING: [Neo4j] Nodes exist but no relationships found.")
```

## 검증 방법 (형님이 직접 확인)

1. **백엔드 터미널 확인**: 프론트에서 방을 클릭할 때 위 DEBUG 메시지가 찍히는지 확인
2. **메시지 개수**: "Returning X messages" 로그가 0이면 SQL 문제, 0이 아닌데 화면에 안 나오면 프론트 문제
3. **그래프 링크**: "Returning X nodes and Y links" 로그에서 Y가 0이면 Neo4j 관계가 실제로 없는 것

## 다음 단계

형님이 위 로그를 확인한 후:
- 메시지가 DB에는 있는데 안 나오면 → SQL WHERE 절 수정
- 그래프 노드는 있는데 선이 없으면 → Neo4j Cypher 쿼리 수정

**"완료"라는 단어는 화면에 실제 데이터가 나올 때까지 사용하지 않겠습니다.**

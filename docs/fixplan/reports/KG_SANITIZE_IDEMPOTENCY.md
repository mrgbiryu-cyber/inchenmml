# KG SANITIZE & IDEMPOTENCY - Knowledge Graph Pollution Prevention

**Issue**: H4 - Ops 메타가 지식 노드로 저장, 에이전트/프롬프트 누적 생성  
**Evidence**: knowledge_service.py, neo4j_client.py, message filtering  
**Goal**: Clean knowledge graph with only domain knowledge, no operational metadata

---

## Evidence Summary

### Knowledge Extraction Pipeline
- **File**: `backend/app/services/knowledge_service.py:74-119`
- **Function**: `process_message_pipeline(message_id)`
- **Flow**:
  1. Load message from RDB
  2. Evaluate importance (`_evaluate_importance()`)
  3. Extract entities with LLM (`_llm_extract()`)
  4. Upsert to Neo4j (`_upsert_to_neo4j()`)

### Importance Filter
- **File**: `backend/app/services/knowledge_service.py:121-137`
```python
def _evaluate_importance(self, content: str) -> bool:
    noise_keywords = [
        "스키마", "마이그레이션", "dual-write", "neo4j", "rdb", "큐", "비동기",
        "프롬프트", "테스트", "로그", "디버그", "에러",
        "API", "라우터", "cors", "토큰", "디렉토리"
    ]
    if len(content) < 10:
        return False
    if any(kw in content.lower() for kw in noise_keywords):
        return False
    return len(content) >= 30
```

**Problem**: Insufficient filtering. Examples of what passes through:
- "새로운 Architect 에이전트를 생성해줘" → "Architect" becomes knowledge node
- "프롬프트를 이렇게 수정해줘: ..." → Prompt text becomes knowledge
- "에이전트 설정을 바꿔줘" → "에이전트 설정" becomes entity

### LLM Extraction
- **File**: `backend/app/services/knowledge_service.py:163-251`
- **Prompt (Line 192-216)**:
```
EXTRACT actionable cognition from the user-assistant exchange.

CAPTURE:
- **Facts**: Definitive statements
- **Tools**: Services, APIs to use
- **Preferences**: User's stated preferences
- **Learnings**: Patterns discovered
```

**Problem**: Too broad. "Create an agent" is a "Tool", "Change agent config" is a "Preference".

### Neo4j Upsert
- **File**: `backend/app/services/knowledge_service.py:275-337`
- **Cypher Query (Line 285-324)**:
```cypher
MERGE (n:Cognition {id: $node_id, project_id: $project_id})
SET n.content = $content, n.type = $node_type, ...
```

**Issue**: No check for "is this operational metadata vs domain knowledge"

### Agent Node Creation
- **File**: `backend/app/core/neo4j_client.py:38-97`
- **Function**: `create_project_graph(project)`
- **Line 60-88**: Creates Agent nodes for each agent in project config

**Issue**: Every time a project is created/updated, new Agent nodes added to graph. If user creates 10 test projects, 10× agent pollution.

---

## Root Cause Analysis

### Pollution Source #1: Operational Conversations

**Scenario**:
```
User: "에이전트 설정 변경해줘"
Master: "어떤 설정을 바꾸실까요?"
User: "Coder 에이전트의 system_prompt를 '코드 리뷰 전문가'로 바꿔줘"
Master: "설정 변경했습니다."
```

**Current Behavior**:
1. All 4 messages pass `_evaluate_importance()` (length > 30, no noise keywords matched)
2. LLM extracts:
   - **Fact**: "Coder 에이전트 system_prompt = 코드 리뷰 전문가"
   - **Tools**: "에이전트 설정 변경"
3. Neo4j nodes created:
   - `Cognition {content: "Coder 에이전트 system_prompt = 코드 리뷰 전문가", type: "Fact"}`
   - `Cognition {content: "에이전트 설정 변경", type: "Tool"}`

**Should Be**: None of this should be in knowledge graph. It's ephemeral ops command, not domain knowledge.

### Pollution Source #2: Self-Referential Agent Creation

**Scenario**:
```
User: "새 프로젝트 만들고 Blog Writer 에이전트 추가해줘"
Master: [Creates project, adds agent]
```

**Current Behavior**:
- "Blog Writer 에이전트" extracted as **Tool**
- If user creates 3 blog projects, "Blog Writer" appears 3 times in knowledge graph

**Should Be**: Agent definitions are in Neo4j project graph, not in Cognition nodes.

### Pollution Source #3: Agent Nodes Duplication

**Evidence**:
- **File**: `backend/app/core/neo4j_client.py:60-88`
- Each `create_project_graph()` call creates Agent nodes
- If project is updated (e.g., agent added), old Agent nodes not deleted

**Result**: Orphaned Agent nodes accumulate

---

## Design Solution

### 1. Enhanced Noise Filter (Content-Based)

**File**: `backend/app/services/knowledge_service.py`

**Current** `_evaluate_importance()`: 15 noise keywords  
**Proposed**: 50+ keywords + pattern matching

```python
def _evaluate_importance(self, content: str, metadata: dict = None) -> bool:
    """
    Filter out operational/meta conversations.
    
    Returns True only if content is domain knowledge.
    """
    # Minimum length
    if len(content) < 30:
        return False
    
    # Expanded noise keywords
    noise_keywords = [
        # Infrastructure/Ops
        "스키마", "마이그레이션", "dual-write", "neo4j", "rdb", "redis", "큐", "비동기",
        "데이터베이스", "인덱스", "쿼리", "트랜잭션",
        
        # Development
        "프롬프트", "시스템 메시지", "테스트", "로그", "디버그", "에러", "버그",
        "코드 리뷰", "리팩토링", "타입스크립트", "파이썬",
        
        # System Management
        "API", "라우터", "엔드포인트", "cors", "토큰", "인증", "권한",
        "디렉토리", "경로", "설정 파일", ".env",
        
        # Agent Operations (NEW)
        "에이전트 생성", "에이전트 추가", "에이전트 삭제", "에이전트 수정",
        "agent_id", "next_agents", "config", "도구 권한",
        "system_prompt", "역할 설정", "워크플로우 편집",
        
        # Project Operations (NEW)
        "프로젝트 생성", "프로젝트 삭제", "tenant_id", "project_id",
        
        # Meta Queries (NEW)
        "설정 어떻게", "어떻게 사용", "명령어", "어떻게 바꿔", "설정 변경"
    ]
    
    content_lower = content.lower()
    
    # Keyword match
    if any(kw in content_lower for kw in noise_keywords):
        return False
    
    # Pattern matching for common operational phrases
    operational_patterns = [
        r"에이전트.*?(생성|추가|수정|삭제|변경)",
        r"프로젝트.*?(만들|생성|삭제)",
        r"설정.*?(바꿔|변경|수정)",
        r"(system_prompt|repo_root|allowed_paths|tool_allowlist)",
        r"워크플로우.*?(편집|수정|변경)",
    ]
    
    import re
    for pattern in operational_patterns:
        if re.search(pattern, content_lower):
            return False
    
    # Check sender role (NEW)
    sender_role = metadata.get("sender_role") if metadata else None
    if sender_role in ["system", "tool"]:
        # System/tool messages are operational, not knowledge
        return False
    
    return True
```

### 2. Role-Based Filtering

**Addition**: Check `sender_role` in MessageModel

**File**: `backend/app/services/knowledge_service.py:process_message_pipeline()`

```python
async def process_message_pipeline(self, message_id: uuid.UUID):
    # Load message
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MessageModel).filter(MessageModel.message_id == message_id))
        msg = result.scalar_one_or_none()
    
    # NEW: Skip non-user, non-assistant messages
    if msg.sender_role not in ["user", "assistant"]:
        logger.debug(f"Skipping knowledge extraction for role={msg.sender_role}")
        return
    
    # Evaluate importance (pass metadata)
    if not self._evaluate_importance(msg.content, metadata={"sender_role": msg.sender_role}):
        logger.debug(f"Message {message_id} filtered as noise")
        return
    
    # Continue extraction...
```

### 3. LLM Prompt Refinement

**File**: `backend/app/services/knowledge_service.py:192-216`

**Current Prompt**:
```
CAPTURE:
- **Facts**: Definitive statements
- **Tools**: Services, APIs to use
- **Preferences**: User's stated preferences
- **Learnings**: Patterns discovered
```

**Proposed Prompt**:
```
EXTRACT domain knowledge from the conversation.

INCLUDE:
- Business logic (e.g., "SEO requires 3+ headings")
- Domain facts (e.g., "Blog posts should be 1500+ words")
- User preferences for domain work (e.g., "Use formal tone for corporate blogs")
- Patterns in domain data (e.g., "Best publish time is 9 AM")

EXCLUDE:
- System operations (e.g., "create agent", "change config")
- Meta requests (e.g., "how to use", "explain workflow")
- Development tasks (e.g., "fix bug", "add feature")
- Agent/project management (e.g., "add Coder agent")

If the conversation is purely operational with no domain knowledge, return:
{
  "nodes": [],
  "edges": [],
  "reason": "No domain knowledge extracted (operational conversation)"
}
```

### 4. Neo4j Agent Node Cleanup

**File**: `backend/app/core/neo4j_client.py`

**Problem**: `create_project_graph()` doesn't delete old nodes

**Proposed**:
```python
async def create_project_graph(self, project: Project):
    """
    Create or update project graph.
    
    Strategy:
    1. Delete old Agent nodes for this project
    2. Create new Agent nodes from current config
    """
    async with self.driver.session() as session:
        # Step 1: Delete old agents for this project
        await session.run(
            """
            MATCH (p:Project {id: $project_id})-[:HAS_AGENT]->(a:Agent)
            DETACH DELETE a
            """,
            project_id=str(project.id)
        )
        
        # Step 2: Create/update project node
        await session.run(
            """
            MERGE (p:Project {id: $project_id})
            SET p.name = $name,
                p.description = $description,
                p.tenant_id = $tenant_id,
                p.updated_at = datetime()
            """,
            project_id=str(project.id),
            name=project.name,
            description=project.description,
            tenant_id=project.tenant_id
        )
        
        # Step 3: Create new agent nodes
        for agent in project.agents:
            await session.run(
                """
                MATCH (p:Project {id: $project_id})
                CREATE (a:Agent {
                    id: $agent_id,
                    role: $role,
                    type: $type,
                    model: $model,
                    provider: $provider
                })
                CREATE (p)-[:HAS_AGENT]->(a)
                """,
                project_id=str(project.id),
                agent_id=agent.agent_id,
                role=agent.role,
                type=agent.type,
                model=agent.model,
                provider=agent.provider
            )
```

### 5. Idempotency for Knowledge Nodes

**Problem**: Same fact extracted multiple times creates duplicates

**File**: `backend/app/services/knowledge_service.py:_upsert_to_neo4j()`

**Current**: Uses `node_id = uuid.uuid4()` → Always new node

**Proposed**: Content-based deduplication
```python
async def _upsert_to_neo4j(self, msg: MessageModel, extracted: Any):
    # ... parse extracted ...
    
    for node in nodes:
        # Generate deterministic ID from content + project
        content_hash = hashlib.sha256(
            f"{project_id}:{node['content']}".encode()
        ).hexdigest()[:16]
        
        node_id = f"cog_{content_hash}"
        
        # MERGE will update if exists, create if not
        await session.run(
            """
            MERGE (n:Cognition {id: $node_id, project_id: $project_id})
            SET n.content = $content,
                n.type = $node_type,
                n.updated_at = datetime(),
                n.source_message_id = $source_msg_id
            """,
            node_id=node_id,
            project_id=str(project_id),
            content=node["content"],
            node_type=node.get("type", "Fact"),
            source_msg_id=str(msg.message_id)
        )
```

---

## Clean-Up Operations

### One-Time Migration Script

**File**: `backend/scripts/cleanup_kg_pollution.py`

```python
"""
Clean up polluted knowledge graph.

Actions:
1. Delete Cognition nodes with operational content
2. Delete duplicate Agent nodes
3. Rebuild project-agent relationships
"""

async def cleanup_operational_cognition():
    """Delete cognition nodes that are clearly operational."""
    noise_patterns = [
        "에이전트 생성", "에이전트 추가", "설정 변경", "프로젝트 만들",
        "system_prompt", "config", "agent_id"
    ]
    
    async with neo4j_client.driver.session() as session:
        for pattern in noise_patterns:
            result = await session.run(
                """
                MATCH (n:Cognition)
                WHERE n.content CONTAINS $pattern
                DELETE n
                RETURN count(n) as deleted
                """,
                pattern=pattern
            )
            count = await result.single()
            print(f"Deleted {count['deleted']} nodes matching '{pattern}'")

async def cleanup_duplicate_agents():
    """Keep only the latest agent nodes per project."""
    async with neo4j_client.driver.session() as session:
        # Find duplicate agents (same agent_id, different nodes)
        await session.run(
            """
            MATCH (p:Project)-[:HAS_AGENT]->(a:Agent)
            WITH a.id as agent_id, collect(a) as agents
            WHERE size(agents) > 1
            UNWIND agents[1..] as duplicate
            DETACH DELETE duplicate
            """
        )
```

**Run-Once**: `python backend/scripts/cleanup_kg_pollution.py`

---

## Monitoring & Health Checks

### Cognition Node Quality Metrics

**Query** (periodic):
```cypher
// Count cognition nodes by type
MATCH (n:Cognition)
RETURN n.type as type, count(n) as count
ORDER BY count DESC
```

**Expected Distribution**:
- Facts: 60-70%
- Tools: 10-20%
- Preferences: 10-20%
- Learnings: 5-10%

**Red Flag**: If "Tools" > 30%, likely pollution (agent commands being stored)

### Agent Node Audit

**Query**:
```cypher
// Find orphaned agents (no project relationship)
MATCH (a:Agent)
WHERE NOT exists((a)<-[:HAS_AGENT]-())
RETURN a.id, a.role
```

**Alert**: If > 0 orphaned agents, run cleanup

---

## Implementation Checklist

- [ ] Expand `_evaluate_importance()` noise keywords to 50+
- [ ] Add regex pattern matching for operational phrases
- [ ] Add `sender_role` filtering (skip system/tool messages)
- [ ] Update LLM extraction prompt with EXCLUDE section
- [ ] Implement content-based `node_id` hashing for idempotency
- [ ] Update `create_project_graph()` to delete old agents first
- [ ] Create `cleanup_kg_pollution.py` script
- [ ] Add Neo4j query functions for node quality metrics
- [ ] Document "What belongs in KG" guidelines

---

## Testing Requirements

### Unit Tests
1. **Noise Filtering**:
   ```python
   assert _evaluate_importance("에이전트 생성해줘") == False
   assert _evaluate_importance("SEO requires 3+ headings") == True
   ```

2. **Content Hashing**:
   ```python
   hash1 = generate_node_id("proj1", "Fact about X")
   hash2 = generate_node_id("proj1", "Fact about X")
   assert hash1 == hash2  # Idempotent
   ```

3. **Agent Node Cleanup**:
   ```python
   # Create project with 3 agents
   await create_project_graph(project)
   # Update to 2 agents
   project.agents = project.agents[:2]
   await create_project_graph(project)
   # Query should return 2 agents, not 3+
   ```

### Integration Tests
1. **Operational Conversation**:
   - Send "에이전트 추가해줘" → Verify 0 cognition nodes created

2. **Domain Knowledge**:
   - Send "Blog posts need 1500+ words for SEO" → Verify 1 Fact node created

3. **Idempotency**:
   - Extract same fact twice → Verify only 1 node in graph (updated timestamp)

---

## Breaking Changes

None - All changes are additive filtering and cleanup.

---

## References

- `backend/app/services/knowledge_service.py` - Extraction pipeline
- `backend/app/core/neo4j_client.py` - Project/agent graph management
- [[COLD_START_AND_DATA_HYGIENE.md](./COLD_START_AND_DATA_HYGIENE.md) - Optional KG policy

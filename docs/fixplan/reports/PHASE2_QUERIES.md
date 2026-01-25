# PHASE 2 QUERIES

**Generated**: 2026-01-24T16:55:00+09:00  
**Phase**: 2 - KG Cleanup + Routing Verification  
**Query Type**: Validation queries for manual execution

---

## 📝 NO QUERIES EXECUTED IN PHASE 2

**Reason**: Phase 2 consisted entirely of code modifications (filtering logic and prompt text changes).  
No database/Neo4j/Redis queries were executed during implementation.

---

## 🔍 RECOMMENDED VALIDATION QUERIES

**USER should run these after deployment to validate Phase 2 changes**:

---

### SQL Query 1: Check Cost Log Status Distribution

**Purpose**: Verify noise filtering is working (more "skip" status)

**Query**:
```sql
SELECT 
    status,
    extraction_type,
    COUNT(*) as count,
    SUM(estimated_cost) as total_cost
FROM cost_logs
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY status, extraction_type
ORDER BY count DESC;
```

**Expected Result**:
- `status = "skip"`: Higher count (operational messages filtered)
- `status = "success"`: Lower count (only domain knowledge)
- Total cost reduced compared to pre-Phase 2

---

### SQL Query 2: Identify Filtered Messages

**Purpose**: See which messages were skipped

**Query**:
```sql
SELECT 
    m.message_id,
    m.sender_role,
    SUBSTRING(m.content, 1, 100) as content_preview,
    c.status,
    c.model_tier
FROM messages m
LEFT JOIN cost_logs c ON m.message_id = c.message_id
WHERE m.timestamp >= NOW() - INTERVAL '24 hours'
AND (c.status = 'skip' OR c.status IS NULL)
ORDER BY m.timestamp DESC
LIMIT 50;
```

**Expected Result**: Messages with operational content ora system/tool roles

---

### Neo4j Query 1: Node Type Distribution (Last 24h)

**Purpose**: Verify cognitive node ratio improved

**Query**:
```cypher
MATCH (n)
WHERE n.created_at >= datetime() - duration('P1D')
WITH labels(n)[0] as node_type, n
RETURN 
    node_type,
    COUNT(n) as count,
    SUM(CASE WHEN n.is_cognitive THEN 1 ELSE 0 END) as cognitive_count,
    ROUND(100.0 * SUM(CASE WHEN n.is_cognitive THEN 1 ELSE 0 END) / COUNT(n), 2) as cognitive_pct
ORDER BY count DESC;
```

**Expected Result**:
- `cognitive_pct` > 60% (Decision, Requirement, Concept, Logic, Task)
- Tool/History nodes < 30%

---

### Neo4j Query 2: Check for Operational Nodes (Should Be Zero)

**Purpose**: Verify operational messages not creating nodes

**Query**:
```cypher
MATCH (n)
WHERE n.created_at >= datetime() - duration('P1D')
AND (
    n.title =~ '.*에이전트.*생성.*'
    OR n.title =~ '.*agent.*create.*'
    OR n.title =~ '.*설정.*변경.*'
    OR n.title =~ '.*button.*click.*'
)
RETURN 
    labels(n)[0] as node_type,
    n.title,
    n.source_message_id,
    n.created_at
ORDER BY n.created_at DESC
LIMIT 20;
```

**Expected Result**: 0 results (no operational nodes created)

---

### Neo4j Query 3: Agent Node Count Per Project

**Purpose**: Monitor agent node accumulation (Task 2.5 not implemented)

**Query**:
```cypher
MATCH (p:Project)-[:HAS_AGENT]->(a:Agent)
RETURN 
    p.id as project_id,
    p.name as project_name,
    COUNT(a) as agent_count
ORDER BY agent_count DESC;
```

**Expected Result**: Agent counts may be higher than expected (cleanup not implemented)  
**Note**: If count grows when updating agent config → Task 2.5 needed

---

### Neo4j Query 4: Find Duplicate Nodes (Task 2.4 Incomplete)

**Purpose**: Check for duplicate knowledge due to lack of content-based IDs

**Query**:
```cypher
MATCH (n)
WHERE n.title IS NOT NULL
WITH n.title as title, n.project_id as pid, labels(n)[0] as type, COLLECT(n) as nodes
WHERE SIZE(nodes) > 1
RETURN 
    type,
    title,
    pid,
    SIZE(nodes) as duplicate_count,
    [node IN nodes | node.id] as node_ids
ORDER BY duplicate_count DESC
LIMIT 20;
```

**Expected Result**: Some duplicates may exist (Task 2.4 incomplete)  
**Action**: If significant duplicates found, complete Task 2.4

---

### Redis Query 1: Check Event Queue Depth

**Purpose**: Monitor knowledge extraction workload

**Query**:
```redis
# Queue depth
LLEN "knowledge_queue"

# Processed count (if event logging implemented in Phase 3)
LLEN "event:*:kg_extracted"
LLEN "event:*:kg_skipped"
```

**Expected Result**: Queue depth low (<10), skip count > extract count

---

## 📊 PERFORMANCE COMPARISON QUERIES

**Run these BEFORE and AFTER deploying Phase 2 changes**:

### Comparison Query 1: Daily LLM Cost

**Before Phase 2**:
```sql
SELECT 
    DATE(timestamp) as date,
    SUM(estimated_cost) as daily_cost,
    COUNT(*) as total_extractions
FROM cost_logs
WHERE extraction_type = 'realtime'
AND timestamp >= NOW() - INTERVAL '7 days'
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

**After Phase 2** (same query):
**Expected Change**: Daily cost reduced by 20-40% due to noise filtering

---

### Comparison Query 2: KG Quality Metrics

**Before Phase 2**:
```cypher
MATCH (n)
WHERE n.created_at >= datetime() - duration('P7D')
RETURN 
    COUNT(n) as total_nodes,
    SUM(CASE WHEN n.is_cognitive THEN 1 ELSE 0 END) as cognitive_nodes,
    ROUND(100.0 * SUM(CASE WHEN n.is_cognitive THEN 1 ELSE 0 END) / COUNT(n), 2) as cognitive_pct;
```

**After Phase 2** (same query):
**Expected Change**: `cognitive_pct` increased from ~40% to >60%

---

## ⚠️ TROUBLESHOOTING QUERIES

### If noise still getting through:

**Check filter effectiveness**:
```sql
SELECT 
    SUBSTRING(m.content, 1, 200) as content,
    c.status,
    c.model_tier
FROM messages m
JOIN cost_logs c ON m.message_id = c.message_id
WHERE c.status = 'success'
AND c.timestamp >= NOW() - INTERVAL '1 hour'
ORDER BY c.timestamp DESC
LIMIT 10;
```

**Action**: If operational content in results → Add more keywords to filter

---

### If role-based filtering not working:

**Check sender_role distribution**:
```sql
SELECT 
    sender_role,
    COUNT(*) as count,
    COUNT(CASE WHEN c.status = 'skip' THEN 1 END) as skipped
FROM messages m
LEFT JOIN cost_logs c ON m.message_id = c.message_id
WHERE m.timestamp >= NOW() - INTERVAL '1 hour'
GROUP BY sender_role
ORDER BY count DESC;
```

**Expected**: system/tool roles should have ~100% skipped

---

## 📝 MANUAL CLEANUP QUERIES (Optional)

**If USER wants to clean existing pollution** (Task 2.6 not executed):

### Delete Operational Cognition Nodes

```cypher
// Preview before deleting
MATCH (n)
WHERE (
    n.title =~ '.*에이전트.*생성.*'
    OR n.title =~ '.*agent.*create.*'
    OR n.title =~ '.*시스템.*설정.*'
    OR n.title =~ '.*button.*'
    OR n.title =~ '.*click.*'
)
RETURN COUNT(n) as nodes_to_delete;

// Execute deletion (after confirming count)
MATCH (n)
WHERE (
    n.title =~ '.*에이전트.*생성.*'
    OR n.title =~ '.*agent.*create.*'
    OR n.title =~ '.*시스템.*설정.*'
    OR n.title =~ '.*button.*'
    OR n.title =~ '.*click.*'
)
DETACH DELETE n;
```

---

### Delete Old Agent Nodes (Task 2.5 workaround)

```cypher
// For each project, keep only latest N agents
MATCH (p:Project)-[r:HAS_AGENT]->(a:Agent)
WITH p, a
ORDER BY a.created_at DESC
WITH p, COLLECT(a) as agents
WHERE SIZE(agents) > 5  // Adjust threshold
UNWIND agents[5..] as old_agent
DETACH DELETE old_agent;
```

---

## ✅ QUERY EXECUTION CHECKLIST

- [ ] Run SQL Query 1 (cost log status) - compare to baseline
- [ ] Run SQL Query 2 (filtered messages) - spot check content
- [ ] Run Neo4j Query 1 (node type distribution) - verify cognitive_pct
- [ ] Run Neo4j Query 2 (operational nodes) - should be 0
- [ ] Run Neo4j Query 3 (agent node count) - monitor accumulation
- [ ] Run Neo4j Query 4 (duplicate nodes) - assess Task 2.4 impact
- [ ] If issues found, run troubleshooting queries
- [ ] (Optional) Run manual cleanup queries for existing pollution

---

**Prepared By**: GPT Implementation Agent  
**Query Status**: VALIDATION QUERIES (not executed)  
**Execution Required**: YES (by USER after deployment)

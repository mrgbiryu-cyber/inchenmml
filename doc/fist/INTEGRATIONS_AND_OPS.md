Part 3: Integrations & Operations
Continued from Part 2
Focus: File System Safety, Roo Code Integration, Knowledge System, Operations, Forbidden Patterns

[PART 6] File System Safety (ZERO TRUST)
6.1 Path Validation (COMPLETE IMPLEMENTATION)
Security Model:

Principle: Trust NOTHING from Job specification
All paths must pass through single validator before ANY file operation
Path Validator Implementation:


from pathlib import Path
from typing import List
import os

class SecurityError(Exception):
    \"\"\"Raised when security validation fails\"\"\"
    pass

def validate_path(
    file_path: str,
    repo_root: str,
    allowed_prefixes: List[str],
    forbidden_patterns: List[str]
) -> Path:
    \"\"\“
    Comprehensive path validation with multiple security layers
    
    Args:
        file_path: Relative or absolute path from Job
        repo_root: Job's project root (absolute)
        allowed_prefixes: Whitelist (e.g., [\"src/\", \"tests/\"])
        forbidden_patterns: Blacklist (e.g., [\"../\", \"~\"])
    
    Returns:
        Validated absolute Path object
    
    Raises:
        SecurityError: If any validation fails
    \"\"\"
    
    # Layer 1: Convert to absolute and resolve symlinks
    try:
        if os.path.isabs(file_path):
            # Absolute paths not allowed in relative context
            raise SecurityError(
                f\"Absolute path not allowed: {file_path}\"
            )
        
        abs_path = (Path(repo_root) / file_path).resolve()
        abs_root = Path(repo_root).resolve()
    except (ValueError, OSError) as e:
        raise SecurityError(f\"Invalid path format: {file_path} ({e})\")
    
    # Layer 2: Ensure path is inside repo_root
    try:
        abs_path.relative_to(abs_root)
    except ValueError:
        raise SecurityError(
            f\"Path traversal detected: {file_path} \"
            f\"escapes {repo_root}\"
        )
    
    # Layer 3: Check forbidden patterns
    path_str = str(abs_path)
    file_path_str = str(file_path)
    
    for pattern in forbidden_patterns:
        if pattern in file_path_str or pattern in path_str:
            raise SecurityError(
                f\"Forbidden pattern '{pattern}' in path: {file_path}\"
            )
    
    # Layer 4: System directory blacklist (absolute protection)
    SYSTEM_DIRS = [
        \"/etc/\", \"/root/\", \"/sys/\", \"/proc/\", \"/boot/\",
        \"/dev/\", \"/var/\", \"/usr/bin/\", \"/usr/sbin/\",
        \"/home/.ssh/\", \"/home/.aws/\", \"/home/.kube/\"
    ]
    
    for sys_dir in SYSTEM_DIRS:
        if path_str.startswith(sys_dir) or sys_dir in path_str:
            raise SecurityError(
                f\"Access to system directory forbidden: {sys_dir}\"
            )
    
    # Layer 5: Whitelist prefix validation
    relative_path = abs_path.relative_to(abs_root)
    relative_str = str(relative_path)
    
    # Special case: root-level files (e.g., README.md)
    # Allow if no directory separator in relative path
    if \"/\" not in relative_str and len(allowed_prefixes) > 0:
        # Root file access only if explicitly allowed via empty prefix
        if \"\" not in allowed_prefixes:
            raise SecurityError(
                f\"Root-level file access not allowed: {file_path}. \"
                f\"Allowed prefixes: {allowed_prefixes}\"
            )
    else:
        # Check if path starts with any allowed prefix
        is_allowed = any(
            relative_str.startswith(prefix) 
            for prefix in allowed_prefixes
        )
        
        if not is_allowed:
            raise SecurityError(
                f\"Path not in allowed directories: {file_path}\n\"
                f\"Allowed prefixes: {allowed_prefixes}\n\"
                f\"Attempted: {relative_str}\"
            )
    
    # Layer 6: Symlink destination validation (if path is symlink)
    if abs_path.is_symlink():
        real_path = abs_path.resolve()
        # Recursively validate the symlink target
        try:
            real_path.relative_to(abs_root)
        except ValueError:
            raise SecurityError(
                f\"Symlink points outside repo_root: {file_path} -> {real_path}\"
            )
    
    return abs_path

# Helper: Validate all paths in a Job
def validate_job_paths(job: dict):
    \"\"\"
    Validate all file paths in a Job before execution
    
    Raises SecurityError on first validation failure
    \"\"\"
    repo_root = job['repo_root']
    allowed = job['allowed_paths']
    forbidden = [
        \"../\", \"~/\", \"~\", \"/etc/\", \"/root/\", \"/sys/\", \"/proc/\"
    ]
    
    # Validate repo_root itself
    if not Path(repo_root).is_absolute():
        raise SecurityError(f\"repo_root must be absolute: {repo_root}\")
    
    if not Path(repo_root).exists():
        raise SecurityError(f\"repo_root does not exist: {repo_root}\")
    
    # Validate each file operation
    for file_op in job.get('file_operations', []):
        file_path = file_op['path']
        
        try:
            validated_path = validate_path(
                file_path,
                repo_root,
                allowed,
                forbidden
            )
            
            logger.debug(f\"✅ Path validated: {file_path} -> {validated_path}\")
            
        except SecurityError as e:
            logger.error(f\"🔒 Path validation failed: {e}\")
            raise
6.2 File Size Limits
Constraints:


# Configuration (from agents.yaml)
MAX_FILE_SIZE = 1048576      # 1 MB per file
MAX_TOTAL_SIZE = 10485760    # 10 MB per job

def validate_file_size(content: str, path: str):
    \"\"\"Check file size before writing\"\"\"
    size_bytes = len(content.encode('utf-8'))
    
    if size_bytes > MAX_FILE_SIZE:
        raise SecurityError(
            f\"File too large: {path} ({size_bytes} bytes, max {MAX_FILE_SIZE})\"
        )

def validate_total_job_size(job: dict):
    \"\"\"Check total size of all files in job\"\"\"
    total = 0
    
    for file_op in job.get('file_operations', []):
        content = file_op.get('content', '')
        total += len(content.encode('utf-8'))
    
    if total > MAX_TOTAL_SIZE:
        raise SecurityError(
            f\"Job total size too large: {total} bytes, max {MAX_TOTAL_SIZE}\"
        )
6.3 Safe File Operations
Wrapper Functions:


def safe_write_file(path: Path, content: str):
    \"\"\“
    Write file with safety checks
    
    - Creates parent directories if needed
    - Sets restrictive permissions (644)
    - Atomic write (temp file + rename)
    \"\"\“
    # Validate size
    validate_file_size(content, str(path))
    
    # Create parent directory
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Atomic write
    temp_path = path.with_suffix('.tmp')
    temp_path.write_text(content, encoding='utf-8')
    temp_path.chmod(0o644)
    temp_path.rename(path)
    
    logger.info(f\"📝 Written: {path} ({len(content)} chars)\")

def safe_read_file(path: Path) -> str:
    \"\"\"
    Read file with safety checks
    
    - Verifies path is validated
    - Size limit on read
    \"\"\"
    if not path.exists():
        raise FileNotFoundError(f\"File not found: {path}\")
    
    size = path.stat().st_size
    if size > MAX_FILE_SIZE:
        raise SecurityError(f\"File too large to read: {path}\")
    
    return path.read_text(encoding='utf-8')

def safe_delete_file(path: Path):
    \"\"\"
    Delete file safely
    
    - Verifies path is validated
    - Logs deletion
    \"\"\"
    if path.exists():
        path.unlink()
        logger.info(f\"🗑️  Deleted: {path}\")
[PART 7] Roo Code Integration
7.1 Integration Model
Design Principle:


Roo Code is NOT a free-form instruction executor.
It ONLY executes structured tasks from signed Jobs.
Execution Flow:


Backend         Local Worker         Roo Code          File System
   │                 │                   │                  │
   │  Job (JSON)     │                   │                  │
   ├────────────────>│                   │                  │
   │                 │                   │                  │
   │                 │ Verify Signature  │                  │
   │                 ├──────────────────>│                  │
   │                 │                   │                  │
   │                 │ Generate TASK.md  │                  │
   │                 ├───────────────────┼─────────────────>│
   │                 │                   │                  │
   │                 │ Trigger Roo Code  │                  │
   │                 ├──────────────────>│                  │
   │                 │                   │                  │
   │                 │                   │ Read TASK.md     │
   │                 │                   ├─────────────────>│
   │                 │                   │                  │
   │                 │                   │ Execute          │
   │                 │                   │ (MiMo LLM)       │
   │                 │                   │                  │
   │                 │                   │ Write files      │
   │                 │                   ├─────────────────>│
   │                 │                   │                  │
   │                 │                   │ Create marker    │
   │                 │                   ├─────────────────>│
   │                 │                   │ .roo_completed   │
   │                 │                   │                  │
   │                 │ Detect marker     │                  │
   │                 │<──────────────────┼──────────────────│
   │                 │                   │                  │
   │                 │ Collect diff      │                  │
   │                 ├───────────────────┼─────────────────>│
   │                 │                   │                  │
   │  Upload result  │                   │                  │
   │<────────────────┤                   │                  │
   │                 │                   │                  │
   │                 │ Cleanup           │                  │
   │                 ├───────────────────┼─────────────────>│
   │                 │ (delete TASK.md)  │                  │
7.2 TASK.md Generation
Template:


def generate_task_md(job: dict, output_path: Path):
    \"\"\“
    Generate Roo Code compatible TASK.md from Job
    
    Args:
        job: Validated Job dictionary
        output_path: Where to write TASK.md (validated path)
    \"\"\"
    
    template = f\"\"\"# CODING TASK
**Generated by**: BUJA Core Platform  
**Job ID**: `{job['job_id']}`  
**Created**: {job['created_at_ts']}  
**Timeout**: {job['timeout_sec']}s  

---

## 🎯 Objective
{job['metadata'].get('objective', 'No objective specified')}

## 📋 Requirements

{format_requirements(job['metadata'].get('requirements', []))}

## 📁 Files to Modify

{format_file_operations(job.get('file_operations', []))}

## ⚙️ Technical Constraints

- **Language**: {job['metadata'].get('language', 'Python')}
- **Framework**: {job['metadata'].get('framework', 'FastAPI')}
- **Code Style**: {job['metadata'].get('code_style', 'Black + isort')}
- **Type Hints**: Required for all functions
- **Docstrings**: Google style

## 🚫 Restrictions

- Do NOT modify files outside: `{job['allowed_paths']}`
- Do NOT import external packages (unless in requirements.txt)
- Do NOT connect to external services

## ✅ Success Criteria

{format_success_criteria(job['metadata'].get('success_criteria', []))}

## 📝 Implementation Notes

{job['metadata'].get('notes', 'No additional notes')}

---

**IMPORTANT**: When complete, create file: `.roo_completed`

**This task is digitally signed and verified. Do not modify this file.**
\"\"\"
    
    safe_write_file(output_path, template)
    logger.info(f\"📄 Generated TASK.md at {output_path}\")

def format_file_operations(operations: List[dict]) -> str:
    \"\"\"Format file operations as markdown list\"\"\"
    if not operations:
        return \"- *(No specific file operations)*\"
    
    lines = []
    for op in operations:
        action = op['action']  # CREATE | MODIFY | DELETE
        path = op['path']
        
        emoji = {\"CREATE\": \"🆕\", \"MODIFY\": \"✏️\", \"DELETE\": \"🗑️\"}.get(action, \"❓\")
        lines.append(f\"{emoji} **{action}** `{path}`\")
        
        if op.get('description'):
            lines.append(f\"   └─ {op['description']}\")
    
    return \"\\n\".join(lines)

def format_requirements(requirements: List[str]) -> str:
    \"\"\"Format requirements as numbered list\"\"\"
    if not requirements:
        return \"*(No specific requirements)*\"
    
    return \"\\n\".join(f\"{i+1}. {req}\" for i, req in enumerate(requirements))

def format_success_criteria(criteria: List[str]) -> str:
    \"\"\"Format success criteria as checklist\"\"\"
    if not criteria:
        return \"- [ ] Task completed\"
    
    return \"\\n\".join(f\"- [ ] {c}\" for c in criteria)
Example Generated TASK.md:


# CODING TASK
**Generated by**: BUJA Core Platform  
**Job ID**: `550e8400-e29b-41d4-a716-446655440000`  
**Created**: 1704067200  
**Timeout**: 600s  

---

## 🎯 Objective
Implement a user authentication endpoint with JWT token generation

## 📋 Requirements

1. Create POST endpoint at `/api/v1/auth/login`
2. Validate credentials against database
3. Generate JWT token with 24h expiry
4. Return token in response

## 📁 Files to Modify

🆕 **CREATE** `src/api/v1/auth.py`
   └─ Authentication endpoints
✏️ **MODIFY** `src/core/security.py`
   └─ Add JWT token generation function
🆕 **CREATE** `tests/test_auth.py`
   └─ Unit tests for authentication

## ⚙️ Technical Constraints

- **Language**: Python 3.10+
- **Framework**: FastAPI 0.109+
- **Code Style**: Black + isort
- **Type Hints**: Required for all functions
- **Docstrings**: Google style

## 🚫 Restrictions

- Do NOT modify files outside: `['src/', 'tests/']`
- Do NOT import external packages (unless in requirements.txt)
- Do NOT connect to external services

## ✅ Success Criteria

- [ ] Endpoint returns 200 on valid credentials
- [ ] Endpoint returns 401 on invalid credentials
- [ ] JWT token contains correct claims
- [ ] All tests pass

## 📝 Implementation Notes

Use bcrypt for password hashing. Token should include user_id, tenant_id, and role.

---

**IMPORTANT**: When complete, create file: `.roo_completed`

**This task is digitally signed and verified. Do not modify this file.**
7.3 Roo Code Trigger & Completion Detection
Trigger Methods:


# Method A: File watcher (if Roo Code supports)
async def trigger_roo_code_watcher(repo_root: Path):
    \"\"\”
    Assumes Roo Code watches for TASK.md changes
    Just creating the file triggers execution
    \"\"\"
    logger.info(f\"✅ TASK.md created. Waiting for Roo Code to detect...\")

# Method B: CLI command (if Roo Code has CLI)
async def trigger_roo_code_cli(repo_root: Path):
    \"\"\“
    Explicitly invoke Roo Code via command line
    \"\"\"
    cmd = [
        \"code\",  # VS Code CLI
        \"--execute-task\",
        str(repo_root / \"TASK.md\")
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=repo_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    logger.info(f\"🚀 Roo Code triggered via CLI\")

# Method C: Wait for Roo Code to pick up automatically
# (Default: just wait for completion marker)
Completion Detection:


async def wait_for_completion(
    repo_root: Path,
    marker_file: str,
    timeout_sec: int
) -> bool:
    \"\"\”
    Wait for Roo Code to create completion marker
    
    Args:
        repo_root: Project root
        marker_file: Name of completion marker (e.g., \".roo_completed\")
        timeout_sec: Maximum wait time
    
    Returns:
        True if completed, raises TimeoutError otherwise
    \"\"\"
    marker_path = repo_root / marker_file
    start_time = asyncio.get_event_loop().time()
    
    logger.info(f\"⏳ Waiting for completion marker: {marker_path}\")
    
    while True:
        # Check if marker exists
        if marker_path.exists():
            logger.info(f\"✅ Completion marker found\")
            
            # Optional: Read marker content (metadata)
            try:
                marker_data = json.loads(marker_path.read_text())
                logger.info(f\"Marker data: {marker_data}\")
            except:
                pass  # Marker can be empty
            
            return True
        
        # Check timeout
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout_sec:
            logger.error(f\"⏱️ Timeout waiting for Roo Code ({timeout_sec}s)\")
            raise TimeoutError(
                f\"Roo Code did not complete within {timeout_sec}s\"
            )
        
        # Wait before next check
        await asyncio.sleep(2)

async def collect_execution_results(job: dict) -> dict:
    \"\"\“
    Collect execution results after Roo Code completion
    
    Returns:
        {
            \"status\": \"COMPLETED\",
            \"output\": {
                \"diff\": \"...\",
                \"files_modified\": [...],
                \"execution_time_ms\": 12500
            }
        }
    \"\"\"
    repo_root = Path(job['repo_root'])
    start_ts = job.get('execution_started_at', time.time())
    
    # 1. Generate git diff
    try:
        diff = subprocess.check_output(
            ['git', 'diff', '--unified=3', 'HEAD'],
            cwd=repo_root,
            text=True,
            timeout=10
        )
    except subprocess.SubprocessError as e:
        logger.warning(f\"Git diff failed: {e}\")
        diff = \"(Git diff unavailable)\"
    
    # 2. Find modified files
    try:
        modified_files = subprocess.check_output(
            ['git', 'diff', '--name-only', 'HEAD'],
            cwd=repo_root,
            text=True,
            timeout=10
        ).strip().split('\\n')
    except subprocess.SubprocessError:
        modified_files = []
    
    # 3. Execution time
    execution_time_ms = int((time.time() - start_ts) * 1000)
    
    # 4. Optional: Collect logs
    log_file = repo_root / '.buja' / 'execution.log'
    execution_log = \"\"
    if log_file.exists():
        execution_log = safe_read_file(log_file)
    
    return {
        \"status\": \"COMPLETED\",
        \"output\": {
            \"diff\": diff,
            \"files_modified\": [f for f in modified_files if f],
            \"execution_time_ms\": execution_time_ms,
            \"execution_log\": execution_log
        },
        \"metrics\": {
            \"lines_added\": diff.count('\\n+'),
            \"lines_removed\": diff.count('\\n-'),
            \"files_touched\": len(modified_files)
        }
    }
7.4 Cleanup

async def cleanup_task_artifacts(repo_root: Path):
    \"\"\“
    Remove temporary files after job completion
    
    - TASK.md
    - .roo_completed
    - .buja/ directory (optional)
    \"\"\"
    task_md = repo_root / \"TASK.md\"
    marker = repo_root / \".roo_completed\"
    buja_dir = repo_root / \".buja\"
    
    for path in [task_md, marker]:
        if path.exists():
            safe_delete_file(path)
    
    # Optional: Remove .buja/ if it was created
    if buja_dir.exists() and buja_dir.is_dir():
        import shutil
        shutil.rmtree(buja_dir)
        logger.info(f\"🗑️  Cleaned up {buja_dir}\")
[PART 8] Knowledge System
8.1 Knowledge Units (Storage Model)
Three Types:


class KnowledgeType(Enum):
    PLAN_TEMPLATE = \"PLAN_TEMPLATE\"    # Reusable project structures
    FIX_PATTERN = \"FIX_PATTERN\"        # Error → Solution mappings
    PROMPT_SNIPPET = \"PROMPT_SNIPPET\"  # Reusable prompts
8.2 Knowledge Retrieval (RAG Pipeline)
Search Flow:


User Query
    ↓
[1. Embedding Generation]
    ↓
[2. Vector Search (Pinecone)]
    ↓ (Top-K: 10)
[3. Graph Expansion (Neo4j)] ← OPTIONAL
    ↓
[4. Re-ranking]
    ↓ (Top-K: 5)
[5. Context Injection]
    ↓
LLM Response
Implementation:


async def search_knowledge(
    query: str,
    user: User,
    knowledge_types: List[KnowledgeType] = None,
    top_k: int = 5
) -> List[dict]:
    \"\"\“
    Hybrid knowledge search (Vector + Graph)
    
    Args:
        query: User's search query
        user: Current user (for tenant isolation)
        knowledge_types: Filter by type (optional)
        top_k: Number of results
    
    Returns:
        List of knowledge items with scores
    \"\"\"
    
    # Step 1: Generate embedding
    embedding = await get_embedding(query)
    
    # Step 2: Vector search (Pinecone)
    namespace = f\"{user.tenant_id}_{user.id}\"
    
    vector_results = index.query(
        vector=embedding,
        top_k=top_k * 2,  # Get more for re-ranking
        namespace=namespace,
        filter={
            \"tenant_id\": user.tenant_id,
            \"type\": {\"$in\": knowledge_types} if knowledge_types else {}
        },
        include_metadata=True
    )
    
    # Step 3: Graph expansion (optional)
    # Find related knowledge via Neo4j relationships
    knowledge_ids = [m.id for m in vector_results.matches]
    
    related = await neo4j_find_related_knowledge(
        knowledge_ids,
        user.tenant_id,
        max_depth=2
    )
    
    # Merge results
    all_results = vector_results.matches + related
    
    # Step 4: Re-ranking
    # Combine vector similarity + graph relevance
    ranked = rerank_results(all_results, query)
    
    return ranked[:top_k]

def rerank_results(results: List, query: str) -> List:
    \"\"\“
    Re-rank results by combining:
    - Vector similarity score
    - Graph connectivity
    - Recency
    - Usage count
    \"\"\"
    scored = []
    
    for result in results:
        score = (
            result.score * 0.6 +                    # Vector similarity
            result.graph_centrality * 0.2 +         # How connected
            result.recency_score * 0.1 +            # How recent
            min(result.usage_count / 100, 1) * 0.1  # How popular
        )
        scored.append((score, result))
    
    return [r for _, r in sorted(scored, reverse=True)]
8.3 Knowledge Archiving (Gardener)
Auto-Archiving Triggers:


# After successful job completion
async def on_job_completed(job_id: str):
    job = await get_job(job_id)
    result = await get_job_result(job_id)
    
    # Archive as Plan Template if multi-step
    if len(job.get('steps', [])) > 1:
        await gardener.archive_plan_template(job, result)
    
    # Archive as Fix Pattern if it was a bug fix
    if 'error' in job['metadata']:
        await gardener.archive_fix_pattern(job, result)
    
    # Extract reusable prompts
    if 'system_prompt' in result:
        await gardener.extract_prompt_snippet(job, result)

class GardenerService:
    \"\"\"Background knowledge management\"\"\"
    
    async def archive_plan_template(self, job: dict, result: dict):
        \"\"\"Extract successful project structure\"\"\"
        
        template = {
            \"type\": \"PLAN_TEMPLATE\",
            \"name\": f\"Pattern from Job {job['job_id'][:8]}\",
            \"structure\": {
                \"steps\": job['steps'],
                \"files_created\": result['output']['files_modified'],
                \"execution_time_ms\": result['output']['execution_time_ms']
            },
            \"tenant_id\": job['tenant_id'],
            \"user_id\": job['user_id'],
            \"created_at\": datetime.now().isoformat()
        }
        
        # Store in Neo4j
        await neo4j_create_knowledge(template)
        
        # Store in Pinecone
        text = f\"Plan: {template['name']}\\nSteps: {', '.join(job['steps'])}\"
        embedding = await get_embedding(text)
        
        index.upsert(
            vectors=[{
                \"id\": f\"plan_{uuid.uuid4()}\",
                \"values\": embedding,
                \"metadata\": template
            }],
            namespace=f\"{job['tenant_id']}_{job['user_id']}\"
        )
    
    async def archive_fix_pattern(self, job: dict, result: dict):
        \"\"\"Store error → solution mapping\"\"\"
        
        error = job['metadata'].get('error', '')
        solution = result['output']['diff']
        
        pattern = {
            \"type\": \"FIX_PATTERN\",
            \"error\": error,
            \"solution\": solution,
            \"language\": job['metadata'].get('language', 'python'),
            \"success_count\": 1,
            \"tenant_id\": job['tenant_id'],
            \"user_id\": job['user_id']
        }
        
        # Similar storage as plan template
        await neo4j_create_knowledge(pattern)
        
        text = f\"Error: {error}\\nSolution: {solution[:500]}\"
        embedding = await get_embedding(text)
        
        index.upsert(
            vectors=[{
                \"id\": f\"fix_{uuid.uuid4()}\",
                \"values\": embedding,
                \"metadata\": pattern
            }],
            namespace=f\"{job['tenant_id']}_{job['user_id']}\"
        )
8.4 Knowledge Update Policy

Auto-Update Triggers:
  - Job completion (successful only)
  - User feedback (like/dislike)
  - Usage metrics (track apply count)

Manual Update:
  - Super Admin can edit any knowledge
  - Users can edit their own knowledge

Versioning:
  - Neo4j stores update history
  - created_at, updated_at timestamps
  - version field (incremental)

Deletion:
  - Soft delete (is_active: false)
  - Hard delete after 30 days (batch job)
  - Super Admin can hard delete immediately
[PART 9] Operations & Monitoring
9.1 Worker Capacity Planning
Concurrent Job Limits:


Per Worker:
  max_concurrent: 3  # From agents.yaml
  
Backend Recommendation:
  - Workers with 16GB RAM: max_concurrent: 3
  - Workers with 32GB RAM: max_concurrent: 5
  - MiMo model memory: ~4GB per instance

Queue Management:
  - If queue > 50 jobs: Alert admin (scale workers)
  - If queue > 100 jobs: Reject new jobs (429)
9.2 Database Maintenance
Redis Cleanup:


# Daily cleanup job (cron)
async def cleanup_redis_expired_keys():
    \"\"\"Remove old job data\"\"\“
    
    # Delete jobs older than 7 days
    cutoff = time.time() - (7 * 86400)
    
    job_keys = await redis.keys(\"job:*:spec\")
    for key in job_keys:
        created_at = await redis.get(key.replace(':spec', ':created_at'))
        if created_at and float(created_at) < cutoff:
            job_id = key.split(':')[1]
            await delete_job_data(job_id)
    
    logger.info(f\"🧹 Cleaned {len(deleted)} old jobs from Redis\")
Neo4j Indexing:


// Create indexes for performance
CREATE INDEX job_tenant_idx FOR (j:Job) ON (j.tenant_id);
CREATE INDEX job_status_idx FOR (j:Job) ON (j.status);
CREATE INDEX knowledge_type_idx FOR (k:Knowledge) ON (k.type);

// Periodic statistics update
MATCH (j:Job {tenant_id: $tenant_id})
RETURN j.status, count(*) as count;
9.3 Cost Monitoring
Daily Cost Report:


async def generate_daily_cost_report(tenant_id: str, date: str):
    \"\"\"Generate cost breakdown\"\"\"
    
    usage_key = f\"usage:{tenant_id}:{date}\"
    usage_data = await redis.hgetall(usage_key)
    
    report = {
        \"date\": date,
        \"tenant_id\": tenant_id,
        \"providers\": {}
    }
    
    for provider in [\"OPENROUTER\", \"OLLAMA\"]:
        key = f\"{provider}_cost\"
        cost = float(usage_data.get(key, 0))
        tokens = int(usage_data.get(f\"{provider}_tokens\", 0))
        
        report[\"providers\"][provider] = {
            \"cost\": cost,
            \"tokens\": tokens,
            \"requests\": int(usage_data.get(f\"{provider}_requests\", 0))
        }
    
    report[\"total_cost\"] = sum(p[\"cost\"] for p in report[\"providers\"].values())
    
    return report
[PART 10] Forbidden Patterns (ABSOLUTE NO)
10.1 Local Worker Violations

# ❌ NEVER do this in Local Worker:

# 1. Decision making
if user_input == \"Create API\":
    intent = \"CODING\"  # ❌ NO! Backend decides intent

# 2. Model selection
if task_complexity > 5:
    model = \"claude-3.5-sonnet\"  # ❌ NO! Backend chooses model

# 3. Direct DB access
result = await neo4j.run(\"MATCH (n) RETURN n\")  # ❌ NO! Only Backend accesses DB

# 4. Modifying job specs
job['timeout_sec'] = 1800  # ❌ NO! Job is immutable

# 5. Inbound network
app.listen(port=8080)  # ❌ NO! Outbound only

# 6. Executing unsigned jobs
if not job.get('signature'):
    execute_anyway()  # ❌ NO! Signature is MANDATORY
10.2 Backend Violations

# ❌ NEVER do this in Backend:

# 1. Trusting client headers
user_id = request.headers.get('X-User-ID')  # ❌ NO! Use JWT only

# 2. Cross-tenant queries without filter
query = \"MATCH (n:Knowledge) RETURN n\"  # ❌ NO! Missing tenant_id

# 3. Hardcoded secrets
API_KEY = \"sk-1234567890\"  # ❌ NO! Use environment variables

# 4. Unsigned job creation
job = {\"job_id\": \"...\", ...}
await redis.rpush(\"job_queue\", job)  # ❌ NO! Must sign first

# 5. Local execution without RBAC check
if execution_location == \"LOCAL_MACHINE\":
    create_job()  # ❌ NO! Check user.role first
Final Directive (CRITICAL)
Assume the Local Worker will eventually be compromised.

Even in worst-case scenario:


✅ Signature prevents job tampering (Worker can't forge jobs)
✅ Path validation prevents file system escape
✅ RBAC prevents privilege escalation (Worker can't access other tenants)
✅ Quota prevents resource abuse
✅ Audit log tracks all suspicious activity
Security is not just preventive—it's also detective and responsive.

Configuration Summary
This completes Part 3 (Integrations & Ops).

Key contents:
✅ Complete Path Validation (multi-layer, production-ready)
✅ Roo Code Integration (TASK.md generation, completion detection)
✅ Knowledge System (RAG pipeline, archiving, retrieval)
✅ Operations (capacity planning, maintenance, cost monitoring)
✅ Forbidden Patterns (comprehensive list of anti-patterns)

🎯 FINAL IMPLEMENTATION CHECKLIST
When implementing, ensure:

Part 1 (Core Design):

 JWT authentication implemented
 Telegram One-Time Link flow working
 RBAC enforced on all endpoints
 Multi-tenancy verified (cross-tenant test)
 Rate limiting active
Part 2 (Job & Security):

 Job signature (Ed25519) working
 Job lifecycle (QUEUED → RUNNING → COMPLETED/FAILED) functional
 Error retry policy implemented
 Worker health check (heartbeat) operational
 Audit logging capturing all security events
Part 3 (Integrations & Ops):

 Path validation blocks all traversal attempts
 Roo Code integration functional (TASK.md → completion)
 Knowledge search (Pinecone + Neo4j) returning results
 Gardener auto-archiving successful jobs
 Cost tracking accurate
Security Verification:

 Penetration test: Try path traversal → Blocked
 Penetration test: Forge job signature → Rejected
 Penetration test: Cross-tenant access → Denied
 Load test: 100 concurrent requests → Handled
 Chaos test: Kill worker mid-job → Job reassigned
END OF SPECIFICATION v3.4

All three parts are now complete. This specification is implementation-ready.
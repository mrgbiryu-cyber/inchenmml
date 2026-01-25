# SYSTEM HEALTH CHECK
## SUMMARY
- **Execution Time**: 2026-01-22 23:06:07
- **OS**: Windows-10-10.0.19045-SP0
- **Python**: 3.14.0 (C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe)
- **Venv**: None

### Core Libraries
- fastapi: 0.128.0
- uvicorn: 0.40.0
- langchain: 1.2.0
- langgraph: 1.0.5
- pydantic: 2.12.4
- sqlalchemy: 2.0.44
- neo4j: 6.0.3
- redis: 7.1.0
- openai: 2.14.0

- **Tests**: 11 (PASS: 10, FAIL: 1, SKIP: 0)
- **PASS%**: 90.9%
- **STATUS**: UNHEALTHY

## FAILURES
| ID | Area | Name | Severity | Message |
|----|------|------|----------|---------|
| DATA-002 | Data | Required Env Vars | HIGH | Missing: NEO4J_URI |

## DETAILS
### COMM-001: Local HTTP Server Test
- **Status**: PASS
- **Area**: Communication
- **Duration**: 144.1ms
- **Message**: Server responded 200 OK

### COMM-002: Timeout Test
- **Status**: PASS
- **Area**: Communication
- **Duration**: 1023.5ms
- **Message**: Timeout occurred as expected

### COMM-003: Internal Module Import
- **Status**: PASS
- **Area**: Communication
- **Duration**: 17424.2ms
- **Message**: All core modules importable

### PERM-001: Tmp File Operations
- **Status**: PASS
- **Area**: Permissions
- **Duration**: 20.9ms
- **Message**: CRUD on tmp_audit success

### PERM-002: Path Independence
- **Status**: PASS
- **Area**: Permissions
- **Duration**: 0.0ms
- **Message**: Path handling looks consistent

### QUEUE-001: Entry Point Discovery
- **Status**: PASS
- **Area**: Queue
- **Duration**: 891.0ms
- **Message**: Found 20 entries
```json
{
  "searched_roots": [
    "D:\\project\\myllm\\backend",
    "D:\\project\\myllm\\local_agent_hub",
    "D:\\project\\myllm\\scripts"
  ],
  "discovered_files": [
    "D:\\project\\myllm\\backend\\check_blog.py",
    "D:\\project\\myllm\\backend\\app\\main.py",
    "D:\\project\\myllm\\backend\\scripts\\test_knowledge_pipeline.py",
    "D:\\project\\myllm\\backend\\tests\\test_security.py",
    "D:\\project\\myllm\\backend\\tools\\auditor\\run_audit.py",
    "D:\\project\\myllm\\local_agent_hub\\main.py",
    "D:\\project\\myllm\\local_agent_hub\\tests\\test_security.py",
    "D:\\project\\myllm\\local_agent_hub\\worker\\executor.py",
    "D:\\project\\myllm\\local_agent_hub\\worker\\poller.py",
    "D:\\project\\myllm\\scripts\\check_blog_project.py",
    "D:\\project\\myllm\\scripts\\generate_keys.py",
    "D:\\project\\myllm\\scripts\\health_check.py",
    "D:\\project\\myllm\\scripts\\test_backend_standalone.py",
    "D:\\project\\myllm\\scripts\\test_domain_permissions.py",
    "D:\\project\\myllm\\scripts\\test_integrations.py",
    "D:\\project\\myllm\\scripts\\test_job.py",
    "D:\\project\\myllm\\scripts\\test_master_agent.py",
    "D:\\project\\myllm\\scripts\\test_orchestration.py",
    "D:\\project\\myllm\\scripts\\test_projects_api.py",
    "D:\\project\\myllm\\scripts\\test_websocket.py"
  ]
}
```

### QUEUE-002: Job Spec Definition
- **Status**: PASS
- **Area**: Queue
- **Duration**: 0.0ms
- **Message**: Pydantic/Schema models found

### CODE-001: Core Package Import
- **Status**: PASS
- **Area**: Code
- **Duration**: 364.1ms
- **Message**: app.main importable

### CODE-002: Syntax Compilation
- **Status**: PASS
- **Area**: Code
- **Duration**: 22.6ms
- **Message**: Python files in backend\app compiled

### DATA-001: Environment Template
- **Status**: PASS
- **Area**: Data
- **Duration**: 0.0ms
- **Message**: Template or .env found

### DATA-002: Required Env Vars
- **Status**: FAIL
- **Area**: Data
- **Duration**: 0.0ms
- **Message**: Missing: NEO4J_URI
- **Fix Hint**: Add to .env or export

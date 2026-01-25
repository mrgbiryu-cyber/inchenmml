# -*- coding: utf-8 -*-
import os
import sys

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import time
import uuid
import subprocess
import importlib.util
import platform
import socket
import threading
import http.server
import compileall
import traceback
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# Constants
AUDIT_VERSION = "v1.5.0"
DEFAULT_TIMEOUT = 10

class Auditor:
    def __init__(self, output_dir: str = ".", timeout: int = DEFAULT_TIMEOUT, verbose: bool = False, skip_network: bool = False):
        self.root_dir = Path(os.getcwd())
        self.output_dir = Path(output_dir)
        self.timeout = timeout
        self.verbose = verbose
        self.skip_network = skip_network
        self.results = []
        self.start_time = datetime.now()
        self.evidence_dir = self.root_dir / "tools" / "auditor" / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        
        # Environment Info
        self.env_info = self._get_env_info()

    def _get_env_info(self) -> Dict[str, Any]:
        info = {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "os": platform.platform(),
            "virtual_env": os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX"),
            "core_libraries": {}
        }
        
        # Select core libraries
        core_libs = ["fastapi", "uvicorn", "langchain", "langgraph", "pydantic", "sqlalchemy", "neo4j", "redis", "openai"]
        try:
            import pkg_resources
            installed = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
            for lib in core_libs:
                if lib in installed:
                    info["core_libraries"][lib] = installed[lib]
        except ImportError:
            # Fallback if pkg_resources not available
            pass
            
        return info

    def add_result(self, test_id: str, area: str, name: str, status: str, severity: str, message: str, evidence: Any = None, fix_hint: str = "", duration_ms: float = 0):
        self.results.append({
            "id": test_id,
            "area": area,
            "name": name,
            "status": status,
            "severity": severity,
            "message": message,
            "evidence": evidence,
            "fix_hint": fix_hint,
            "duration_ms": duration_ms
        })
        if self.verbose:
            print(f"[{status}] {test_id}: {name} ({duration_ms:.1f}ms)")

    # --- A. Communication (COMM) ---
    async def run_comm_audits(self):
        if self.skip_network:
            self.add_result("COMM-001", "Communication", "Local HTTP Server Test", "SKIP", "LOW", "Skipped by flag")
            self.add_result("COMM-002", "Communication", "Timeout Test", "SKIP", "LOW", "Skipped by flag")
            return

        # COMM-001: Local Dummy Server
        start = time.time()
        try:
            class DummyHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"OK")
                def log_message(self, format, *args): pass

            port = 9876
            server = http.server.HTTPServer(('127.0.0.1', port), DummyHandler)
            thread = threading.Thread(target=server.serve_forever)
            thread.daemon = True
            thread.start()

            import urllib.request
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}', timeout=2) as response:
                    res_body = response.read().decode()
                    if response.status == 200 and res_body == "OK":
                        self.add_result("COMM-001", "Communication", "Local HTTP Server Test", "PASS", "MED", "Server responded 200 OK", duration_ms=(time.time()-start)*1000)
                    else:
                        self.add_result("COMM-001", "Communication", "Local HTTP Server Test", "FAIL", "MED", f"Unexpected response: {response.status}", fix_hint="Check local network stack")
            finally:
                server.shutdown()
                server.server_close()
        except Exception as e:
            self.add_result("COMM-001", "Communication", "Local HTTP Server Test", "FAIL", "HIGH", str(e))

        # COMM-002: Intentional Timeout
        start = time.time()
        try:
            class TimeoutHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    time.sleep(2) # Exceeds 1s timeout
                    self.send_response(200)
                    self.end_headers()
                def log_message(self, format, *args): pass

            port = 9877
            server = http.server.HTTPServer(('127.0.0.1', port), TimeoutHandler)
            thread = threading.Thread(target=server.serve_forever)
            thread.daemon = True
            thread.start()

            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}', timeout=1) as response:
                    self.add_result("COMM-002", "Communication", "Timeout Test", "FAIL", "MED", "Timeout did not occur", fix_hint="Check socket timeout handling")
            except socket.timeout:
                self.add_result("COMM-002", "Communication", "Timeout Test", "PASS", "MED", "Timeout occurred as expected", duration_ms=(time.time()-start)*1000)
            except Exception as e:
                self.add_result("COMM-002", "Communication", "Timeout Test", "FAIL", "MED", str(e))
            finally:
                server.shutdown()
                server.server_close()
        except Exception as e:
            self.add_result("COMM-002", "Communication", "Timeout Test", "FAIL", "MED", str(e))

        # COMM-003: Internal Modules Import
        start = time.time()
        modules = ["app.core.config", "app.core.neo4j_client", "app.services.master_agent_service"]
        missing = []
        # Add backend to path for import check
        sys.path.append(str(self.root_dir / "backend"))
        for mod in modules:
            try:
                importlib.import_module(mod)
            except Exception as e:
                missing.append(f"{mod}: {str(e)}")
        
        if not missing:
            self.add_result("COMM-003", "Communication", "Internal Module Import", "PASS", "HIGH", "All core modules importable", duration_ms=(time.time()-start)*1000)
        else:
            self.add_result("COMM-003", "Communication", "Internal Module Import", "FAIL", "HIGH", f"Import failures: {', '.join(missing)}", fix_hint="Check PYTHONPATH or missing dependencies")

    # --- B. Permissions/Filesystem (PERM) ---
    def run_perm_audits(self):
        start = time.time()
        # PERM-001: Write/Read/Delete
        tmp_dir = self.root_dir / "tmp_audit"
        try:
            tmp_dir.mkdir(exist_ok=True)
            test_file = tmp_dir / "audit_test.txt"
            content = "AUDIT_DATA_" + str(uuid.uuid4())
            test_file.write_text(content)
            read_back = test_file.read_text()
            if read_back == content:
                test_file.unlink()
                tmp_dir.rmdir()
                self.add_result("PERM-001", "Permissions", "Tmp File Operations", "PASS", "HIGH", "CRUD on tmp_audit success", duration_ms=(time.time()-start)*1000)
            else:
                self.add_result("PERM-001", "Permissions", "Tmp File Operations", "FAIL", "HIGH", "Read back mismatch", fix_hint="Check disk integrity or disk full")
        except Exception as e:
            self.add_result("PERM-001", "Permissions", "Tmp File Operations", "FAIL", "HIGH", str(e))

        # PERM-002: Path Processing (OS Independence)
        try:
            p1 = Path("data/logs/test.log")
            if "\\" in str(p1) and platform.system() != "Windows":
                 self.add_result("PERM-002", "Permissions", "Path Independence", "FAIL", "MED", "Suspected hardcoded backslash on non-Windows")
            elif "/" in str(p1) and platform.system() == "Windows" and False: # Windows handles / fine
                 pass
            else:
                 self.add_result("PERM-002", "Permissions", "Path Independence", "PASS", "MED", "Path handling looks consistent")
        except:
            self.add_result("PERM-002", "Permissions", "Path Independence", "FAIL", "LOW", "Error testing path")

    # --- C. Queue/Jobs/Workers (QUEUE) ---
    def run_queue_audits(self):
        # Entry Point Discovery
        start = time.time()
        discovered_entries = []
        evidence = {"searched_roots": [], "discovered_files": []}
        
        search_roots = [self.root_dir / "backend", self.root_dir / "local_agent_hub", self.root_dir / "scripts"]
        for root in search_roots:
            if not root.exists(): continue
            evidence["searched_roots"].append(str(root))
            for path in root.rglob("*.py"):
                # Skip virtual environments and node_modules in search
                if any(x in path.parts for x in [".venv", "venv", "node_modules", "__pycache__"]):
                    continue
                    
                if path.name in ["main.py", "run.py", "poller.py", "executor.py", "worker.py"]:
                    discovered_entries.append(str(path))
                    evidence["discovered_files"].append(str(path))
                else:
                    # Check for if __name__ == "__main__"
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            if 'if __name__ == "__main__":' in content:
                                discovered_entries.append(str(path))
                                evidence["discovered_files"].append(str(path))
                    except: pass

        if discovered_entries:
            self.add_result("QUEUE-001", "Queue", "Entry Point Discovery", "PASS", "HIGH", f"Found {len(discovered_entries)} entries", evidence=evidence, duration_ms=(time.time()-start)*1000)
        else:
            self.add_result("QUEUE-001", "Queue", "Entry Point Discovery", "FAIL", "HIGH", "No execution entry points found", evidence=evidence, fix_hint="Create main.py or add __main__ block")

        # QUEUE-002: Job Spec Validation
        try:
            # Look for schema.json or similar
            schema_found = False
            for path in self.root_dir.rglob("*schema*.py"):
                if "AgentDefinition" in path.read_text(errors="ignore"):
                    schema_found = True
                    break
            if schema_found:
                self.add_result("QUEUE-002", "Queue", "Job Spec Definition", "PASS", "MED", "Pydantic/Schema models found")
            else:
                self.add_result("QUEUE-002", "Queue", "Job Spec Definition", "SKIP", "LOW", "No explicit job schema found")
        except: pass

    # --- D. Code Integrity (CODE) ---
    def run_code_audits(self):
        # CODE-001: Packge Import
        start = time.time()
        try:
            import app.main
            self.add_result("CODE-001", "Code", "Core Package Import", "PASS", "HIGH", "app.main importable", duration_ms=(time.time()-start)*1000)
        except Exception as e:
             self.add_result("CODE-001", "Code", "Core Package Import", "FAIL", "HIGH", str(e), fix_hint="Check backend structure")

        # CODE-002: Compilation Check
        start = time.time()
        try:
            # Scope compilation to backend/app instead of entire backend/ to avoid .venv
            target = self.root_dir / "backend" / "app"
            if not target.exists():
                target = self.root_dir / "backend"
            
            # Use a regex to skip .venv if we are at backend root
            success = compileall.compile_dir(str(target), quiet=1, rx=re.compile(r'[\\/]node_modules[\\/]|[\\/]\.venv[\\/]'))
            if success:
                self.add_result("CODE-002", "Code", "Syntax Compilation", "PASS", "HIGH", f"Python files in {target.relative_to(self.root_dir)} compiled", duration_ms=(time.time()-start)*1000)
            else:
                self.add_result("CODE-002", "Code", "Syntax Compilation", "FAIL", "HIGH", "Syntax errors detected in source code", fix_hint="Run python -m compileall backend/app")
        except Exception as e:
            self.add_result("CODE-002", "Code", "Syntax Compilation", "FAIL", "MED", str(e))

    # --- E. Data/Env (DATA) ---
    def run_data_audits(self):
        # DATA-001: .env.example
        if (self.root_dir / ".env.example").exists() or (self.root_dir / "backend" / ".env").exists():
            self.add_result("DATA-001", "Data", "Environment Template", "PASS", "LOW", "Template or .env found")
        else:
            self.add_result("DATA-001", "Data", "Environment Template", "FAIL", "MED", "No .env or .env.example found", fix_hint="Create .env.example")

        # DATA-002: Required Env Vars
        required = ["OPENROUTER_API_KEY", "NEO4J_URI"]
        missing = [v for v in required if not os.environ.get(v)]
        if not missing:
            self.add_result("DATA-002", "Data", "Required Env Vars", "PASS", "HIGH", "All critical env vars present")
        else:
            self.add_result("DATA-002", "Data", "Required Env Vars", "FAIL", "HIGH", f"Missing: {', '.join(missing)}", fix_hint="Add to .env or export")

    def generate_reports(self):
        # Calculate summary
        total = len(self.results)
        passes = len([r for r in self.results if r["status"] == "PASS"])
        fails = len([r for r in self.results if r["status"] == "FAIL"])
        skips = len([r for r in self.results if r["status"] == "SKIP"])
        
        pass_ratio = passes / (passes + fails) if (passes + fails) > 0 else 0
        status = "HEALTHY"
        if fails > 0: status = "UNHEALTHY"
        elif skips > 0: status = "DEGRADED"

        # MD Report
        md = [
            "# SYSTEM HEALTH CHECK",
            "## SUMMARY",
            f"- **Execution Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **OS**: {self.env_info['os']}",
            f"- **Python**: {self.env_info['python_version'].split()[0]} ({self.env_info['python_executable']})",
            f"- **Venv**: {self.env_info['virtual_env'] or 'None'}",
            "",
            "### Core Libraries",
        ]
        for lib, ver in self.env_info["core_libraries"].items():
            md.append(f"- {lib}: {ver}")
            
        md.extend([
            "",
            f"- **Tests**: {total} (PASS: {passes}, FAIL: {fails}, SKIP: {skips})",
            f"- **PASS%**: {pass_ratio:.1%}",
            f"- **STATUS**: {status}",
            "",
            "## FAILURES",
            "| ID | Area | Name | Severity | Message |",
            "|----|------|------|----------|---------|",
        ])
        
        for r in self.results:
            if r["status"] == "FAIL":
                md.append(f"| {r['id']} | {r['area']} | {r['name']} | {r['severity']} | {r['message']} |")
                
        md.extend([
            "",
            "## DETAILS",
        ])
        
        for r in self.results:
            md.append(f"### {r['id']}: {r['name']}")
            md.append(f"- **Status**: {r['status']}")
            md.append(f"- **Area**: {r['area']}")
            md.append(f"- **Duration**: {r['duration_ms']:.1f}ms")
            md.append(f"- **Message**: {r['message']}")
            if r["fix_hint"]:
                md.append(f"- **Fix Hint**: {r['fix_hint']}")
            if r["evidence"]:
                md.append(f"```json\n{json.dumps(r['evidence'], indent=2, ensure_ascii=False)}\n```")
            md.append("")

        (self.output_dir / "SYSTEM_HEALTH_CHECK.md").write_text("\n".join(md), encoding="utf-8")

        # JSON Report
        json_out = {
            "summary": {
                "timestamp": datetime.now().isoformat(),
                "env": self.env_info,
                "stats": {"total": total, "pass": passes, "fail": fails, "skip": skips},
                "status": status,
                "pass_ratio": pass_ratio
            },
            "results": self.results
        }
        (self.output_dir / "SYSTEM_HEALTH_CHECK.json").write_text(json.dumps(json_out, indent=2), encoding="utf-8")
        
        print(f"\nAudit Complete: {status} ({pass_ratio:.1%})")
        print(f"Reports generated: SYSTEM_HEALTH_CHECK.md, SYSTEM_HEALTH_CHECK.json")

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--skip-network", action="store_true")
    args = parser.parse_args()

    auditor = Auditor(output_dir=args.output_dir, timeout=args.timeout, verbose=args.verbose, skip_network=args.skip_network)
    
    print("MYLLM System Health Audit Starting...")
    
    await auditor.run_comm_audits()
    auditor.run_perm_audits()
    auditor.run_queue_audits()
    auditor.run_code_audits()
    auditor.run_data_audits()
    
    auditor.generate_reports()

if __name__ == "__main__":
    asyncio.run(main())

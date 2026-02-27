#!/usr/bin/env python3
"""
Production integration smoke check:
1) /health composite component check
2) auth register -> token
3) projects list/create/get (read-after-write)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Tuple


def _request_json(
    method: str,
    url: str,
    payload: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
    timeout: int = 10,
) -> Tuple[int, Dict[str, Any]]:
    body = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=body, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            return status, data
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"detail": raw}
        return e.code, data


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP timeout (sec)")
    parser.add_argument("--username", default="", help="Optional username")
    parser.add_argument("--password", default="", help="Optional password")
    parser.add_argument("--tenant-id", default="tenant_verify", help="Tenant id for register")
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL", ""), help="Optional direct Redis URL")
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", ""), help="Optional direct Neo4j URI")
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", ""), help="Optional direct Neo4j user")
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""), help="Optional direct Neo4j password")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    ts = int(time.time())
    username = args.username or f"verify_{ts}"
    password = args.password or "VerifyPass!123"

    print(f"[1/5] health check: {base}/health")
    status, health = _request_json("GET", f"{base}/health", timeout=args.timeout)
    _assert(status == 200, f"/health returned {status}: {health}")
    _assert("components" in health, "/health missing components")
    components = health.get("components", {})
    for name in ("redis", "postgresql", "neo4j"):
        _assert(name in components, f"/health missing component: {name}")
    print("[OK] /health components present")

    print("[2/5] register")
    register_qs = urllib.parse.urlencode(
        {"username": username, "password": password, "tenant_id": args.tenant_id}
    )
    register_url = f"{base}/api/v1/auth/register?{register_qs}"
    reg_status, reg_data = _request_json("POST", register_url, timeout=args.timeout)
    if reg_status not in (200, 201, 400):
        raise RuntimeError(f"register failed: {reg_status} {reg_data}")
    if reg_status == 400:
        print("[INFO] user already exists, continuing with token step")
    else:
        print("[OK] register completed")

    print("[3/5] token")
    tok_status, tok_data = _request_json(
        "POST",
        f"{base}/api/v1/auth/token",
        payload={"username": username, "password": password},
        timeout=args.timeout,
    )
    _assert(tok_status == 200, f"token failed: {tok_status} {tok_data}")
    access_token = tok_data.get("access_token", "")
    _assert(access_token != "", "token response missing access_token")
    authz = {"Authorization": f"Bearer {access_token}"}
    print("[OK] token issued")

    print("[4/5] projects list")
    list_status, list_data = _request_json(
        "GET",
        f"{base}/api/v1/projects/",
        headers=authz,
        timeout=args.timeout,
    )
    _assert(list_status == 200, f"projects list failed: {list_status} {list_data}")
    if not isinstance(list_data, list):
        raise RuntimeError("projects list response is not a list")
    print(f"[OK] projects listed: {len(list_data)}")

    print("[5/5] create project + read-after-write")
    project_name = f"verify-project-{ts}"
    create_status, create_data = _request_json(
        "POST",
        f"{base}/api/v1/projects/",
        payload={
            "name": project_name,
            "description": "integration smoke test",
            "project_type": "GROWTH_SUPPORT",
        },
        headers=authz,
        timeout=args.timeout,
    )
    _assert(create_status in (200, 201), f"project create failed: {create_status} {create_data}")
    project_id = create_data.get("id", "")
    _assert(project_id != "", "project create response missing id")

    get_status, get_data = _request_json(
        "GET",
        f"{base}/api/v1/projects/{project_id}",
        headers=authz,
        timeout=args.timeout,
    )
    _assert(get_status == 200, f"project read-after-write failed: {get_status} {get_data}")
    _assert(get_data.get("id") == project_id, "created project id does not match fetched project id")
    print("[OK] read-after-write passed")

    # Optional direct Redis write-read check.
    if args.redis_url:
        print("[6/7] redis write-read")
        try:
            import redis as redis_sync
        except Exception as exc:
            raise RuntimeError(f"redis package import failed: {exc}") from exc
        redis_client = redis_sync.Redis.from_url(
            args.redis_url,
            decode_responses=True,
            socket_timeout=args.timeout,
            socket_connect_timeout=args.timeout,
        )
        redis_key = f"verify:smoke:{ts}"
        redis_val = str(ts)
        redis_client.setex(redis_key, 60, redis_val)
        redis_read = redis_client.get(redis_key)
        _assert(redis_read == redis_val, "redis read-after-write mismatch")
        print("[OK] redis read-after-write passed")
    else:
        print("[SKIP] redis write-read (no --redis-url)")

    # Optional direct Neo4j write-read-delete check.
    if args.neo4j_uri and args.neo4j_user and args.neo4j_password:
        print("[7/7] neo4j write-read-delete")
        try:
            from neo4j import GraphDatabase
        except Exception as exc:
            raise RuntimeError(f"neo4j package import failed: {exc}") from exc
        driver = GraphDatabase.driver(
            args.neo4j_uri,
            auth=(args.neo4j_user, args.neo4j_password),
            connection_timeout=args.timeout,
        )
        marker = f"verify-{ts}"
        with driver.session() as session:
            session.run(
                "MERGE (n:SmokeVerify {id: $id}) SET n.updated_at = datetime()",
                id=marker,
            )
            row = session.run(
                "MATCH (n:SmokeVerify {id: $id}) RETURN n.id AS id",
                id=marker,
            ).single()
            _assert(row is not None and row["id"] == marker, "neo4j read-after-write mismatch")
            session.run("MATCH (n:SmokeVerify {id: $id}) DETACH DELETE n", id=marker)
        driver.close()
        print("[OK] neo4j write-read-delete passed")
    else:
        print("[SKIP] neo4j write-read (missing --neo4j-uri/user/password)")

    print("PASS: production integration smoke check completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

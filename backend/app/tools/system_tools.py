import redis.asyncio as redis
import json
import time
from datetime import datetime
from typing import List, Dict, Any
from app.core.config import settings
from app.models.schemas import JobStatus
from langchain.tools import tool

@tool
async def get_active_jobs_tool() -> str:
    """
    현재 시스템에서 실행 중인 모든 작업(QUEUED, RUNNING)의 상태를 실시간으로 조회합니다.
    """
    jobs = await get_job_history_internal(limit=10, active_only=True)
    if not jobs:
        return "현재 실행 중인 활성 작업이 없습니다."
    
    output = ["### [실시간 활성 작업 목록]"]
    for j in jobs:
        output.append(f"- **Job ID**: `{j['job_id']}`")
        output.append(f"  - **상태**: {j['status']}")
        output.append(f"  - **역할**: {j['role']}")
        output.append(f"  - **프로젝트**: {j['project_id']}")
        output.append(f"  - **모델**: {j['model']}")
    return "\n".join(output)

@tool
async def get_job_history_tool(limit: int = 10) -> str:
    """
    최근 실행된 모든 작업(완료, 실패 포함)의 이력과 저장 경로(repo_path)를 실시간으로 가져옵니다.
    작업의 이력이나 결과 파일 위치를 물을 때 반드시 이 도구를 사용하십시오.
    """
    jobs = await get_job_history_internal(limit=limit)
    if not jobs:
        return "최근 작업 이력이 없습니다."
    
    output = ["### [최근 작업 실행 이력]"]
    output.append("| 작업 ID | 상태 | 실행일시 | 역할 | 저장경로 |")
    output.append("|---------|------|----------|------|----------|")
    for j in jobs:
        output.append(f"| `{j['job_id']}` | {j['status']} | {j['created_at']} | {j['role']} | `{j['repo_path']}` |")
    
    return "\n".join(output)

async def get_job_history_internal(limit: int = 20, active_only: bool = False) -> List[Dict[str, Any]]:
    """
    최근 작업 이력(완료 포함)을 실시간으로 조회합니다. (내부용)
    """
    try:
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        jobs = []
        async for key in r.scan_iter("job:*:status"):
            try:
                status = await r.get(key)
                
                if active_only and status not in [JobStatus.QUEUED.value, JobStatus.RUNNING.value]:
                    continue
                    
                job_id = key.split(":")[1]
                spec_json = await r.get(f"job:{job_id}:spec")
                created_at_raw = await r.get(f"job:{job_id}:created_at")
                
                if spec_json:
                    spec = json.loads(spec_json)
                    metadata = spec.get("metadata", {})
                    
                    # 날짜 변환 (방어 코드 추가)
                    date_str = "Unknown"
                    ts = 0
                    try:
                        if created_at_raw:
                            ts = int(float(created_at_raw))
                            date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        pass

                    jobs.append({
                        "job_id": job_id,
                        "status": status,
                        "created_at": date_str,
                        "timestamp": ts,
                        "role": metadata.get("role") or spec.get("metadata", {}).get("role", "Unknown"),
                        "project_id": metadata.get("project_id") or spec.get("metadata", {}).get("project_id", "Unknown"),
                        "repo_path": spec.get("repo_root") or spec.get("repo_path", "N/A"),
                        "model": spec.get("model")
                    })
            except Exception as inner_e:
                print(f"Error processing job key {key}: {inner_e}")
                continue
        
        await r.close()
        
        # 최신순 정렬
        jobs.sort(key=lambda x: x['timestamp'], reverse=True)
        return jobs[:limit]
    except Exception as e:
        print(f"Error fetching job history: {e}")
        return []

async def get_active_jobs():
    """Compatibility for existing calls"""
    return await get_job_history_internal(limit=10, active_only=True)

async def get_job_history(limit: int = 20):
    """Compatibility for existing calls"""
    return await get_job_history_internal(limit=limit)

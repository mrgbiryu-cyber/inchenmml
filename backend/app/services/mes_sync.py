# -*- coding: utf-8 -*-
"""
MES Sync - v3.2
MES (Mission Execution Spec) 동기화 및 VERIFIED 상태 관리
"""
import hashlib
import json
from typing import Dict, Any

from app.models.stream_context import StreamContext


async def load_current_mes_and_state(ctx: StreamContext) -> StreamContext:
    """
    Step 4: MES 및 Verification 상태 로드 (<= 150줄)
    
    역할:
    - 현재 세션/프로젝트의 MES와 verification_state를 Redis/DB에서 로드
    - 없으면 빈 MES, DIRTY로 초기화
    - 여기서는 절대 "설정 미비" 같은 판단 문구를 만들지 않음 (로딩만)
    """
    from app.core.neo4j_client import neo4j_client
    
    ctx.add_log("load_current_mes_and_state", f"Loading MES for project {ctx.project_id}...")
    
    try:
        # Neo4j에서 프로젝트 조회
        project_data = await neo4j_client.get_project(ctx.project_id)
        
        if project_data and project_data.get("agent_config"):
            # MES 로드 (agent_config가 MES)
            ctx.mes = project_data.get("agent_config", {})
            ctx.add_log("load_current_mes_and_state", f"MES loaded: {len(ctx.mes.get('agents', []))} agents")
            
            # MES Hash 계산
            ctx.mes_hash = compute_mes_hash(ctx.mes)
            ctx.add_log("load_current_mes_and_state", f"MES Hash: {ctx.mes_hash[:8]}...")
        else:
            # 빈 MES 초기화
            ctx.mes = {"agents": [], "workflow_type": "SEQUENTIAL", "entry_agent_id": ""}
            ctx.mes_hash = compute_mes_hash(ctx.mes)
            ctx.add_log("load_current_mes_and_state", "MES not found, initialized empty")
        
        # [TODO] Redis/DB에서 verification_state 로드
        # 지금은 임시로 DIRTY로 초기화
        ctx.verification_state = "DIRTY"
        ctx.verified_hash = None
        
    except Exception as e:
        ctx.add_log("load_current_mes_and_state", f"Error loading MES: {e}")
        # 로딩 실패 시에도 빈 MES로 초기화
        ctx.mes = {}
        ctx.mes_hash = None
        ctx.verification_state = "DIRTY"
    
    return ctx


async def sync_mes_if_needed(ctx: StreamContext) -> StreamContext:
    """
    Step 5: MES 동기화 (<= 200줄)
    
    역할:
    - REQUIREMENT intent일 때:
      - Draft(현재 session_id)에서 MES 자동 매칭 ("초안 반영")
      - 사용자 입력에서 MES 필드 직접 수정 신호가 있으면 반영
    
    강제 규칙 (필수):
    - MES가 조금이라도 바뀌면:
      - verification_state = DIRTY
      - verified_hash = None
    - category별 "최신 Draft 1개만" MES에 반영
    """
    if ctx.primary_intent != "REQUIREMENT":
        ctx.add_log("sync_mes_if_needed", "Skipped (not REQUIREMENT)")
        return ctx
    
    ctx.add_log("sync_mes_if_needed", "Syncing MES from Drafts...")
    
    # Draft → MES 매칭
    from app.core.database import get_drafts_from_rdb
    
    try:
        # 현재 세션의 UNVERIFIED Draft 조회
        drafts = await get_drafts_from_rdb(session_id=ctx.session_id, status="UNVERIFIED")
        
        if drafts:
            # category별 최신 Draft 1개만 선택
            latest_by_category = {}
            for draft in drafts:
                category = draft.category if hasattr(draft, 'category') else draft['category']
                timestamp = draft.timestamp if hasattr(draft, 'timestamp') else draft['timestamp']
                
                if category not in latest_by_category or timestamp > latest_by_category[category]['timestamp']:
                    latest_by_category[category] = {
                        'content': draft.content if hasattr(draft, 'content') else draft['content'],
                        'timestamp': timestamp
                    }
            
            # MES에 반영 (간단한 예시)
            mes_updated = False
            for category, draft_data in latest_by_category.items():
                content = draft_data['content']
                
                # [간단한 매핑 예시] 실제로는 더 정교하게 구현 필요
                if category == "환경":
                    if ctx.mes.get("environment") != content:
                        ctx.mes["environment"] = content
                        mes_updated = True
                elif category == "목표":
                    if ctx.mes.get("objective") != content:
                        ctx.mes["objective"] = content
                        mes_updated = True
                elif category == "산출물":
                    if ctx.mes.get("deliverable") != content:
                        ctx.mes["deliverable"] = content
                        mes_updated = True
                elif category == "제약":
                    if ctx.mes.get("constraints") != content:
                        ctx.mes["constraints"] = content
                        mes_updated = True
            
            if mes_updated:
                ctx.mes_changed = True
                ctx.add_log("sync_mes_if_needed", f"MES updated from Drafts: {list(latest_by_category.keys())}")
                
                # [Guardrail 원칙 3] MES 변경 시 무조건 VERIFIED 해제
                ctx.verification_state = "DIRTY"
                ctx.verified_hash = None
                ctx.add_log("sync_mes_if_needed", "[Guardrail] MES changed → VERIFIED = DIRTY")
            else:
                ctx.add_log("sync_mes_if_needed", "No MES changes from Drafts")
        else:
            ctx.add_log("sync_mes_if_needed", "No UNVERIFIED Drafts found")
    
    except Exception as e:
        ctx.add_log("sync_mes_if_needed", f"Error syncing MES: {e}")
    
    return ctx


def compute_mes_hash(mes: Dict[str, Any]) -> str:
    """
    Step 6: MES Hash 계산 (<= 120줄)
    
    역할:
    - Hash 정규화 후 해시 생성
    - key sorting, strip, 연속 공백 축약
    """
    if not mes:
        return hashlib.sha256(b"").hexdigest()
    
    # 정규화
    def normalize_value(v):
        if isinstance(v, str):
            # strip + 연속 공백 축약
            return ' '.join(v.strip().split())
        elif isinstance(v, dict):
            return {k: normalize_value(val) for k, val in sorted(v.items())}
        elif isinstance(v, list):
            return [normalize_value(item) for item in v]
        else:
            return v
    
    normalized = {k: normalize_value(v) for k, v in sorted(mes.items())}
    
    # JSON 직렬화 (sort_keys=True)
    raw_json = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    
    # SHA256 해시
    return hashlib.sha256(raw_json.encode('utf-8')).hexdigest()

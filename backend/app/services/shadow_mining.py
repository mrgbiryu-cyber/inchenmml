# -*- coding: utf-8 -*-
"""
Shadow Mining Service - v3.2
자연어 대화에서 설계 정보를 임시로 추출하여 Draft로 저장
"""
import sys
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import re
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.master import Draft
from app.core.config import settings

class ShadowMiningService:
    """
    Shadow Mining 엔진
    - 자연어에서 설계 정보 추출 (환경, 목표, 산출물, 제약)
    - Draft로 저장 (UNVERIFIED 상태)
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="google/gemini-2.0-flash-001",
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.3,  # 추출 작업이므로 낮은 temperature
        )
    
    async def extract_design_info(
        self, 
        user_input: str, 
        session_id: str,
        user_id: str,
        project_id: str = None
    ) -> List[Draft]:
        """
        자연어에서 설계 정보 추출
        
        Args:
            user_input: 사용자 입력
            session_id: 현재 세션 ID
            user_id: 사용자 ID
            project_id: 프로젝트 ID (optional)
        
        Returns:
            List[Draft]: 추출된 Draft 리스트
        """
        
        # 1. 설계 정보 추출이 필요한지 먼저 판단
        if not self._is_design_relevant(user_input):
            return []
        
        # 2. LLM으로 설계 정보 추출
        system_prompt = """
당신은 설계 정보 추출 전문가입니다.
사용자의 자연어 입력에서 프로젝트 설계 관련 정보를 추출하세요.

**카테고리:**
- 환경: 개발 환경, 플랫폼, 언어, 프레임워크 (예: "로컬", "파이썬", "웹")
- 목표: 프로젝트의 목적, 달성하고자 하는 것 (예: "현재 시간 출력", "API 테스트")
- 산출물: 생성할 파일, 결과물 (예: "now.py 파일", "리포트")
- 제약: 제한 사항, 조건 (예: "외부 라이브러리 사용 금지", "1시간 내 완료")

**출력 형식 (JSON 배열):**
[
    {"category": "환경", "content": "로컬, 파이썬"},
    {"category": "목표", "content": "현재 시간 출력"},
    {"category": "산출물", "content": "now.py 파일"}
]

**규칙:**
1. 설계 정보가 없으면 빈 배열 [] 반환
2. 감정, 잡담, 농담은 무시
3. 명시적 정보만 추출 (추측 금지)
4. 중복 제거
"""
        
        user_prompt = f"사용자 입력: \"{user_input}\"\n\n위 입력에서 설계 정보를 추출하세요."
        
        try:
            messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            
            # JSON 추출 (```json ... ``` 감싸져 있을 수 있음)
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                content = json_match.group(1)
            
            # JSON 파싱
            extracted_data = json.loads(content)
            
            if not isinstance(extracted_data, list):
                return []
            
            # Draft 객체 생성
            drafts = []
            for item in extracted_data:
                if not isinstance(item, dict) or "category" not in item or "content" not in item:
                    continue
                
                # 카테고리 검증
                if item["category"] not in ["환경", "목표", "산출물", "제약"]:
                    continue
                
                draft = Draft(
                    session_id=session_id,
                    user_id=user_id,
                    project_id=project_id,
                    category=item["category"],
                    content=item["content"],
                    status="UNVERIFIED",
                    source="USER_UTTERANCE"
                )
                drafts.append(draft)
            
            # [v3.2 Guardrail] 카테고리당 최신 1개만 유효
            # 동일 category 존재 시 이전 Draft는 SUPERSEDED로 변경
            if drafts:
                await self._supersede_old_drafts(session_id, drafts)
            
            return drafts
        
        except Exception as e:
            print(f"⚠️ Shadow Mining 실패: {e}", flush=True)
            return []
    
    async def _supersede_old_drafts(self, session_id: str, new_drafts: List[Draft]):
        """
        [v3.2 Guardrail] 카테고리당 최신 1개만 유효
        동일 category의 이전 Draft는 SUPERSEDED로 변경
        
        ❌ Draft를 누적 병합하지 않음
        ❌ 과거 세션 Draft를 참조하지 않음
        """
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import Table, MetaData, update
        
        try:
            from app.core.database import AsyncEngine
            metadata = MetaData()
            drafts_table = Table('drafts', metadata, autoload_with=AsyncEngine)
            
            # 새로운 Draft의 카테고리 목록
            new_categories = [draft.category for draft in new_drafts]
            
            async with AsyncSessionLocal() as session:
                # 동일 session_id + category의 UNVERIFIED Draft를 SUPERSEDED로 변경
                stmt = update(drafts_table).where(
                    drafts_table.c.session_id == session_id,
                    drafts_table.c.category.in_(new_categories),
                    drafts_table.c.status == 'UNVERIFIED'
                ).values(status='SUPERSEDED')
                
                await session.execute(stmt)
                await session.commit()
                
                print(f"✅ [Guardrail] 카테고리 {new_categories} 이전 Draft SUPERSEDED 처리 완료", flush=True)
        
        except Exception as e:
            print(f"⚠️ [Guardrail] Draft supersede 실패: {e}", flush=True)
    
    def _is_design_relevant(self, text: str) -> bool:
        """
        입력이 설계 관련 정보를 포함하는지 빠르게 판단
        (LLM 호출 전 필터링)
        """
        # 잡담 패턴 (설계 정보 없음)
        chitchat_patterns = [
            r"^(안녕|하이|ㅎㅇ|고마워|ㅋㅋ|ㅎㅎ)$",
            r"^(응|예|좋아|네|ok)$",
        ]
        for pattern in chitchat_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        # 설계 관련 키워드 (최소한의 필터)
        design_keywords = [
            "파일", "코드", "프로젝트", "환경", "개발", "생성", "만들",
            "API", "데이터", "서버", "클라이언트", "테스트", "배포",
            "로컬", "원격", "파이썬", "자바", "웹", "앱", "시스템"
        ]
        
        return any(keyword in text for keyword in design_keywords)

# Singleton instance
shadow_mining_service = ShadowMiningService()


# === [v3.2 Refactor] Step 3: extract_shadow_draft ===

async def extract_shadow_draft(ctx: "StreamContext") -> "StreamContext":
    """
    Step 3: Shadow Draft 추출 (<= 200줄)
    
    역할:
    - NATURAL(또는 HAS_BRAINSTORM_SIGNAL flag)일 때만 Draft 채굴
    - Draft는 반드시 UNVERIFIED, session_id, category를 가짐
    - 카테고리: goal, deliverable, symptom, environment, constraints
    - 동일 category 존재 시 이전 Draft는 SUPERSEDED
    """
    from app.models.stream_context import StreamContext
    
    # 조건: NATURAL 또는 HAS_BRAINSTORM_SIGNAL flag
    if ctx.primary_intent != "NATURAL" and "HAS_BRAINSTORM_SIGNAL" not in ctx.flags:
        ctx.add_log("extract_shadow_draft", "Skipped (not NATURAL and no BRAINSTORM flag)")
        return ctx
    
    ctx.add_log("extract_shadow_draft", "Extracting design info from user input...")
    
    # Shadow Mining 실행
    drafts = await shadow_mining_service.extract_design_info(
        user_input=ctx.user_input_norm,
        session_id=ctx.session_id,
        user_id=ctx.user_id or "system",
        project_id=ctx.project_id
    )
    
    if drafts:
        ctx.draft_updates = [
            {
                "id": draft.id,
                "category": draft.category,
                "content": draft.content,
                "status": draft.status,
                "timestamp": draft.timestamp
            }
            for draft in drafts
        ]
        ctx.add_log("extract_shadow_draft", f"Extracted {len(drafts)} drafts: {[d.category for d in drafts]}")
    else:
        ctx.add_log("extract_shadow_draft", "No design info extracted")
    
    return ctx

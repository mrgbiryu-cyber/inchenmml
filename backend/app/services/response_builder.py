# -*- coding: utf-8 -*-
"""
Response Builder - v3.2
최종 응답 생성 전담 (자동 부착 제거 포함)
"""
import re
from typing import List

from app.models.stream_context import StreamContext


async def handle_function_read(ctx: StreamContext) -> StreamContext:
    """
    Step 7: FUNCTION_READ 처리 (<= 200줄)
    
    역할:
    - primary_intent == FUNCTION_READ일 때만 실행
    - 반드시 실시간 Tool/DB 조회만
    - KG/RAG/Vector/Neo4j 결과는 "호출 자체를 스킵" 또는 "결과를 폐기"
    
    실패 시 고정 템플릿 (필수):
    "사용자님, 현재 프로젝트 상태를 최신으로 조회할 수 없어 확인되지 않은 내용을 단정해서 말씀드릴 수 없습니다. (조회 도구 접근 오류)"
    """
    if ctx.primary_intent != "FUNCTION_READ":
        ctx.add_log("handle_function_read", "Skipped (not FUNCTION_READ)")
        return ctx
    
    ctx.add_log("handle_function_read", "Executing real-time DB/Tool query...")
    
    # [Guardrail 원칙 4] KG/RAG/Vector 차단, 실시간 Tool만 사용
    from app.services.master_agent_service import get_project_details
    
    try:
        # 실시간 Tool 호출
        details = await get_project_details.ainvoke({"project_id": ctx.project_id})
        
        if not details or "없음" in details or "N/A" in details:
            # [Guardrail] 조회 실패 시 고정 템플릿
            ctx.tool_error = "조회 도구 접근 오류"
            ctx.tool_facts = {}
            ctx.add_log("handle_function_read", "Query failed or empty result")
        else:
            # [Guardrail] 추론 없이 순수 DB 결과만 저장
            ctx.tool_facts["project_details"] = details
            ctx.add_log("handle_function_read", "Query successful")
    
    except Exception as e:
        # [Guardrail] 예외 발생 시 고정 템플릿
        ctx.tool_error = f"조회 도구 접근 오류: {str(e)}"
        ctx.tool_facts = {}
        ctx.add_log("handle_function_read", f"Query exception: {e}")
    
    return ctx


async def handle_function_write_gate(ctx: StreamContext) -> StreamContext:
    """
    Step 8: FUNCTION_WRITE Gate 평가 (<= 200줄)
    
    역할:
    - primary_intent == FUNCTION_WRITE일 때만 평가
    - WRITE 수행 자체는 여기서 하지 않고, "Gate Open/Closed"만 결정
    
    Gate Open 조건 (AND):
    1. intent == FUNCTION_WRITE
    2. verification_state == VERIFIED
    3. current_mes_hash == verified_hash
    4. confirm_token_present == True (명시 토큰만)
    
    Closed일 때 안내 (필수):
    "사용자님, 설계(요구사항)가 변경되어 확정이 해제되었습니다. 다시 '실행 확정'으로 확정해 주셔야 합니다."
    """
    if ctx.primary_intent != "FUNCTION_WRITE":
        ctx.add_log("handle_function_write_gate", "Skipped (not FUNCTION_WRITE)")
        return ctx
    
    ctx.add_log("handle_function_write_gate", "Evaluating WRITE Gate...")
    
    # [Guardrail 원칙 5] 4조건 AND 검증
    
    # 조건 1: intent == FUNCTION_WRITE (이미 확인됨)
    ctx.add_log("handle_function_write_gate", "✅ Condition 1: intent == FUNCTION_WRITE")
    
    # 조건 2: verification_state == VERIFIED
    if ctx.verification_state != "VERIFIED":
        ctx.write_gate_open = False
        ctx.write_gate_reason = "사용자님, 설계(요구사항)가 변경되어 확정이 해제되었습니다. 다시 '실행 확정'으로 확정해 주셔야 합니다."
        ctx.add_log("handle_function_write_gate", "❌ Condition 2 failed: verification_state != VERIFIED")
        return ctx
    
    ctx.add_log("handle_function_write_gate", "✅ Condition 2: verification_state == VERIFIED")
    
    # 조건 3: current_mes_hash == verified_hash
    if ctx.mes_hash != ctx.verified_hash:
        ctx.write_gate_open = False
        ctx.write_gate_reason = "사용자님, 설계(요구사항)가 변경되어 확정이 해제되었습니다. 다시 '실행 확정'으로 확정해 주셔야 합니다."
        ctx.add_log("handle_function_write_gate", f"❌ Condition 3 failed: mes_hash ({ctx.mes_hash[:8]}...) != verified_hash ({ctx.verified_hash[:8] if ctx.verified_hash else 'None'}...)")
        return ctx
    
    ctx.add_log("handle_function_write_gate", "✅ Condition 3: current_mes_hash == verified_hash")
    
    # 조건 4: confirm_token_present == True (명시 토큰만)
    if not ctx.confirm_token_detected:
        ctx.write_gate_open = False
        ctx.write_gate_reason = "사용자님, 명시적 확정 토큰이 필요합니다. 정확히 '실행 확정', '변경 확정', 또는 'START TASK 실행'을 입력해주세요."
        ctx.add_log("handle_function_write_gate", "❌ Condition 4 failed: confirm_token not detected")
        return ctx
    
    ctx.add_log("handle_function_write_gate", "✅ Condition 4: confirm_token_present == True")
    
    # 모든 조건 통과 → Gate Open
    ctx.write_gate_open = True
    ctx.write_gate_reason = None
    ctx.add_log("handle_function_write_gate", "🚪 Gate OPEN - WRITE allowed")
    
    return ctx


def response_builder(ctx: StreamContext) -> StreamContext:
    """
    Step 9: 최종 응답 생성 (<= 200줄)
    
    역할:
    - NATURAL/REQUIREMENT: 부드러운 대화 + MES 진행률 안내 (모드 전환 선언 금지)
    - FUNCTION_READ: tool_facts를 그대로 요약 (추론 금지)
    - FUNCTION_WRITE: Gate Open 시에만 "다음 행동 가능" 안내
    
    자동 부착 제거 (필수):
    - 아래는 intent != FUNCTION_WRITE 또는 Gate Closed면 무조건 제거:
      - MISSION READINESS REPORT
      - READY_TO_START JSON
    """
    ctx.add_log("response_builder", f"Building response for intent: {ctx.primary_intent}")
    
    response_parts = []
    
    # === NATURAL / REQUIREMENT ===
    if ctx.primary_intent in ["NATURAL", "REQUIREMENT"]:
        # [v3.2.1 FIX] NATURAL과 REQUIREMENT 모두 LLM이 응답을 생성하므로 여기서는 빈 응답
        # response_builder는 플레이스홀더만 설정 (LLM이 덮어씀)
        response_parts.append("")  # LLM이 응답 생성
        
        # [Guardrail] Shadow Mining 결과가 있으면 간단히 언급
        if ctx.draft_updates:
            response_parts.append(f"\n\n_(참고: 설계 정보 {len(ctx.draft_updates)}개가 임시 저장되었습니다.)_")
    
    # === FUNCTION_READ ===
    elif ctx.primary_intent == "FUNCTION_READ":
        # [Guardrail 원칙 4] tool_facts를 그대로 출력 (추론 금지)
        if ctx.tool_error:
            # [Guardrail] 고정 템플릿
            response_parts.append(f"사용자님, 현재 프로젝트 상태를 최신으로 조회할 수 없어 확인되지 않은 내용을 단정해서 말씀드릴 수 없습니다. ({ctx.tool_error})")
        elif ctx.tool_facts:
            # [중요] "안녕 근데 현황 보여줘" 같은 혼합 발화 처리
            if "HAS_NATURAL_SIGNAL" in ctx.flags:
                response_parts.append("안녕하세요! 😊\n\n")
            
            response_parts.append("📊 [실시간 DB 조회] 현재 프로젝트 상태:\n\n")
            response_parts.append(ctx.tool_facts.get("project_details", "조회 결과 없음"))
        else:
            response_parts.append("사용자님, 조회 결과가 없습니다.")
    
    # === FUNCTION_WRITE ===
    elif ctx.primary_intent == "FUNCTION_WRITE":
        if ctx.write_gate_open:
            # [Guardrail] Gate Open 시에만 다음 행동 가능 안내
            response_parts.append("✅ 모든 조건이 충족되었습니다. [START TASK] 버튼을 눌러 작업을 시작하세요.\n\n")
            response_parts.append(f'{{"status": "READY_TO_START", "project_id": "{ctx.project_id}", "mes_hash": "{ctx.mes_hash}"}}')
        else:
            # [Guardrail] Gate Closed 시 안내
            response_parts.append(ctx.write_gate_reason or "실행 조건이 충족되지 않았습니다.")
    
    # === CANCEL / TOPIC_SHIFT ===
    elif ctx.primary_intent in ["CANCEL", "TOPIC_SHIFT"]:
        # [수정] TOPIC_SHIFT도 자연스러운 대화 + 안내로 처리
        if ctx.primary_intent == "CANCEL":
            response_parts.append("알겠습니다. 현재 진행 중이던 작업 계획이 초기화되었습니다. 새로운 지시를 내려주세요.")
        else:
            # TOPIC_SHIFT: 간단한 안내만 (자연스러운 대화는 NATURAL LLM이 담당)
            response_parts.append("\n\n_(새로운 주제로 대화를 시작합니다. 이전 작업 계획이 있었다면 초기화되었습니다.)_")
    
    # 최종 응답 조합
    ctx.final_response = "".join(response_parts)
    
    # [Guardrail 원칙 6] 자동 부착 제거 (intent != FUNCTION_WRITE 또는 Gate Closed)
    if ctx.primary_intent != "FUNCTION_WRITE" or not ctx.write_gate_open:
        ctx.final_response = _remove_auto_attachments(ctx.final_response)
    
    ctx.add_log("response_builder", f"Response built: {len(ctx.final_response)} chars")
    
    return ctx


def _remove_auto_attachments(content: str) -> str:
    """
    자동 부착 제거 (필수)
    
    제거 대상:
    - MISSION READINESS REPORT
    - READY_TO_START JSON
    - 기타 자동 생성 블록
    """
    patterns = [
        # MISSION READINESS REPORT
        r"---\s*MISSION READINESS REPORT\s*---[\s\S]*?(?=\n\n|\Z)",
        r"\[준비 상태 점검 완료\][\s\S]*?(?=\n\n|\Z)",
        
        # READY_TO_START JSON (단, FUNCTION_WRITE + Gate Open일 때는 제거하지 않음)
        r'```json\s*\{\s*"status"\s*:\s*"READY_TO_START"[\s\S]*?```',
        
        # 조치 방법 가이드
        r"## 조치 방법 가이드[\s\S]*?(?=\n\n|\Z)",
        r"\*\*권장 조치:\*\*[\s\S]*?(?=\n\n|\Z)",
    ]
    
    for pattern in patterns:
        content = re.sub(pattern, "", content, flags=re.MULTILINE | re.DOTALL)
    
    # 연속 빈 줄 제거
    content = re.sub(r"\n{3,}", "\n\n", content)
    
    return content.strip()

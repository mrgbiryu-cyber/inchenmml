# -*- coding: utf-8 -*-
"""
Intent Router - v3.2
Intent 분류 전담 (Primary Intent 1개 + Secondary Flags)
"""
import re
from typing import Tuple, List

from app.models.stream_context import StreamContext
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# [v3.2 Guardrail] 명시적 confirm_token만 인정
CONFIRM_TOKENS = ["실행 확정", "변경 확정", "START TASK 실행"]


async def detect_topic_shift_with_context(ctx: StreamContext) -> bool:
    """
    이전 대화 맥락을 보고 주제 변경 여부 판단 (LLM 활용)
    
    Returns:
        True: 완전히 다른 주제로 변경됨
        False: 연속된 대화 또는 판단 불가
    """
    try:
        from app.core.database import get_messages_from_rdb
        from app.core.config import settings
        
        # 1. 이전 3~5개 대화 가져오기
        recent_messages = await get_messages_from_rdb(
            ctx.project_id, 
            ctx.thread_id, 
            limit=5
        )
        
        if len(recent_messages) < 2:
            ctx.add_log("topic_shift", "대화 시작 단계 - 주제 변경 아님")
            return False  # 대화 시작이면 주제 변경 아님
        
        # 2. LLM에게 맥락 판단 요청
        llm = ChatOpenAI(
            model="google/gemini-2.0-flash-001",  # 빠르고 저렴한 모델
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.1,
        )
        
        # 최근 3개 메시지만 사용 (너무 길면 노이즈)
        history = "\n".join([
            f"{m.sender_role}: {m.content[:100]}..."  # MessageModel 객체 접근
            for m in recent_messages[-3:]
        ])
        
        prompt = f"""이전 대화와 현재 입력의 연관성을 판단하세요.

이전 대화:
{history}

현재 입력: {ctx.user_input_raw}

질문: 현재 입력이 이전 대화와 **완전히 다른 주제**인가요?

판단 기준:
- YES: 완전히 다른 주제 (예: GPT 성능 얘기하다가 → "오늘 날씨 어때?")
- NO: 연속된 대화 (예: GPT 성능 얘기 중 → "다른 모델은 어때?", "그럼 어떻게 해결해?")

**답변은 "YES" 또는 "NO" 한 단어만 출력하세요.**

답변:"""
        
        response = await llm.ainvoke(prompt)
        result = "YES" in response.content.upper()
        
        ctx.add_log("topic_shift", f"LLM 판단: {'주제 변경' if result else '연속 대화'}")
        return result
        
    except Exception as e:
        ctx.add_log("topic_shift", f"LLM 판단 실패: {e} - False로 처리")
        return False  # 실패 시 안전하게 연속 대화로 처리


def parse_user_input(ctx: StreamContext) -> StreamContext:
    """
    Step 1: 입력 정규화 (<= 150줄)
    
    역할:
    - 공백/줄바꿈 정리
    - confirm_token 감지 (명시 토큰만)
    """
    # 입력 정규화
    raw = ctx.user_input_raw
    norm = raw.strip()
    
    # 연속 공백 축약
    norm = re.sub(r'\s+', ' ', norm)
    
    ctx.user_input_norm = norm
    ctx.add_log("parse_user_input", f"Normalized: '{norm}'")
    
    # [Guardrail] confirm_token 감지 (명시 토큰만)
    for token in CONFIRM_TOKENS:
        if token in norm:
            ctx.confirm_token = token
            ctx.confirm_token_detected = True
            ctx.add_log("parse_user_input", f"Confirm token detected: '{token}'")
            break
    
    # [Guardrail] "응", "예", "좋아"는 confirm_token으로 인정하지 않음
    # (아무 처리도 하지 않음, False 고정)
    
    return ctx


async def classify_intent(ctx: StreamContext) -> StreamContext:
    """
    Step 2: Intent 분류 (<= 200줄) - 가장 중요
    
    [v3.2.1 보완] 원칙: LLM 판정 실패 시, **기본값은 무조건 NATURAL**로 설정
    
    규칙:
    - Primary Intent는 1개만
    - Secondary 신호는 flags로만
    - **명시적 키워드가 없으면 모두 NATURAL로 처리** (보수적 접근)
    
    판정 우선순위:
    1. CANCEL (명시적 키워드만: "취소", "중단", "그만", "abort")
    2. FUNCTION_WRITE (confirm_token이 명시 토큰일 때만)
    3. FUNCTION_READ (명확한 조회 패턴)
    4. REQUIREMENT (명확한 작업 요청 패턴)
    5. NATURAL (그 외 모든 경우 - 기본값)
    
    예외 처리:
    - 긴 인사 ("부자야 오늘 날씨도 좋은데 고생이 많다") → NATURAL
    - 외국어 인사 ("Hello Buja") → NATURAL
    - 모호한 명령 ("이거 좀 봐봐") → NATURAL
    """
    msg = ctx.user_input_norm
    msg_lower = msg.lower()
    
    ctx.add_log("classify_intent", f"Classifying: '{msg}'")
    
    # === 우선순위 1: CANCEL (명시적 키워드만) ===
    # [v3.2.1] 확실한 취소 신호만 인정
    cancel_tokens = ["취소", "중단", "그만", "abort"]
    if any(token in msg_lower for token in cancel_tokens):
        ctx.set_primary_intent("CANCEL")
        ctx.add_log("classify_intent", f"명시적 CANCEL 토큰 감지: {msg}")
        return ctx
    
    # === 우선순위 2: FUNCTION_WRITE (confirm_token 필수) ===
    # [v3.2.1] 명시적 확정 토큰만 인정 (CONFIRM_TOKENS: "실행 확정", "변경 확정", "START TASK 실행")
    if ctx.confirm_token_detected:
        ctx.set_primary_intent("FUNCTION_WRITE")
        ctx.add_flag("HAS_CONFIRM_TOKEN")
        ctx.add_log("classify_intent", f"명시적 FUNCTION_WRITE 토큰 감지: {ctx.confirm_token}")
        return ctx
    
    # === 우선순위 3: FUNCTION_READ (엄격한 조회 패턴만) ===
    # [v3.2.1] "현재", "지금" 같은 일상어는 너무 광범위하므로 더 엄격한 조합만 허용
    strict_read_patterns = [
        r"^(현재|지금).*(프로젝트|에이전트|워커|상태|구성|설정).*(보여|알려|확인)",  # "현재 프로젝트 보여줘"
        r"^(등록된|목록|리스트).*(보여|알려|확인)",  # "등록된 목록 보여줘"
        r"(프로젝트|에이전트|워커).*(상태|현황|목록).*(조회|확인|보여|알려)",  # "프로젝트 상태 조회"
    ]
    
    for pattern in strict_read_patterns:
        if re.search(pattern, msg):
            ctx.set_primary_intent("FUNCTION_READ")
            ctx.add_log("classify_intent", f"엄격한 FUNCTION_READ 패턴 감지")
            
            # [Guardrail] 혼합 발화 감지
            if any(kw in msg for kw in ["안녕", "고마워", "ㅋㅋ"]):
                ctx.add_flag("HAS_NATURAL_SIGNAL")
            
            return ctx
    
    # === 우선순위 4: REQUIREMENT (명확한 작업 요청만) ===
    # [v3.2.1] 작업성 발화만 인정 (단순 아이디어는 NATURAL로)
    strict_requirement_patterns = [
        r"(만들어|생성|구현|추가|수정|고쳐).*(줘|주세요|해줘|해 주세요)",  # "만들어줘", "수정해줘"
        r"(설계|계획|정리|요약).*(해줘|하자|해 주세요)",  # "설계해줘", "정리하자"
        r"프로젝트.*(만들|생성|수정|구현|추가)",  # "프로젝트 만들어"
        r"(오류|에러|버그|문제).*(고쳐|수정|해결).*(줘|주세요|해줘)",  # "오류 고쳐줘"
    ]
    
    for pattern in strict_requirement_patterns:
        if re.search(pattern, msg):
            ctx.set_primary_intent("REQUIREMENT")
            ctx.add_flag("HAS_REQUIREMENT_SIGNAL")
            ctx.add_log("classify_intent", f"명확한 REQUIREMENT 패턴 감지")
            return ctx
    
    # === 우선순위 5: TOPIC_SHIFT (극도로 명확한 경우만) ===
    # [v3.2.1] 주제 변경은 매우 명시적인 경우만 인정
    explicit_topic_shift_patterns = [
        r"^(새로|다시|처음부터).*(시작|해줘)$",  # "새로 시작해줘"
        r"주제.*바꿔",  # "주제 바꿔"
        r"다른.*얘기",  # "다른 얘기 하자"
    ]
    
    for pattern in explicit_topic_shift_patterns:
        if re.search(pattern, msg):
            ctx.set_primary_intent("TOPIC_SHIFT")
            ctx.add_log("classify_intent", "명시적 TOPIC_SHIFT 패턴 감지")
            return ctx
    
    # ================================================================
    # === [v3.2.1 핵심] 기본값: NATURAL (모든 예외 케이스 처리) ===
    # ================================================================
    # 위의 명시적 패턴에 매칭되지 않으면 모두 NATURAL로 처리
    # 이로써 다음 케이스들이 안전하게 처리됨:
    # - 긴 인사: "부자야 오늘 날씨도 좋은데 고생이 많다"
    # - 외국어 인사: "Hello Buja", "Bonjour"
    # - 모호한 명령: "이거 좀 봐봐", "저거 어떻게 됐어?"
    # - 단순 감정 표현: "ㅋㅋㅋ", "오 대박", "와 신기하다"
    
    ctx.set_primary_intent("NATURAL")
    ctx.add_log("classify_intent", f"명시적 패턴 미감지 → NATURAL (기본값 정책)")
    
    # [Guardrail] Flag 신호 감지 (응답 품질 향상용)
    if any(kw in msg for kw in ["파일", "코드", "프로젝트", "API", "데이터베이스", "서버"]):
        ctx.add_flag("HAS_BRAINSTORM_SIGNAL")
        ctx.add_log("classify_intent", "설계 관련 키워드 감지 → HAS_BRAINSTORM_SIGNAL 추가")
    
    if any(kw in msg for kw in ["상태", "현황", "어떻게", "어떤"]):
        ctx.add_flag("HAS_STATUS_SIGNAL")
    
    return ctx

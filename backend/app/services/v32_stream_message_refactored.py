# -*- coding: utf-8 -*-
"""
v3.2 stream_message - Refactored
오케스트레이션만 수행 (실제 로직은 전부 위임)
"""
import uuid
from typing import AsyncGenerator, List, Dict, Any, Optional

from app.models.stream_context import StreamContext
from app.models.master import ChatMessage, ConversationMode, MasterIntent # [v4.0]
from app.core.database import save_message_to_rdb
from app.services.knowledge_service import knowledge_queue # [v4.2] Knowledge Ingestion

# Step 함수들 import
from app.services.intent_router import parse_user_input, classify_intent
from app.services.shadow_mining import extract_shadow_draft
from app.services.mes_sync import load_current_mes_and_state, sync_mes_if_needed, compute_mes_hash
from app.services.response_builder import handle_function_read, handle_function_write_gate, response_builder


from app.services.debug_service import debug_service  # [v4.2]
from app.schemas.debug import DebugInfo, RetrievalChunk, RetrievalDebug  # [v4.2]

async def stream_message_v32(
    message: str,
    history: List[ChatMessage],
    project_id: str = None,
    thread_id: str = None,
    user: Any = None,
    worker_status: Dict[str, Any] = None,
    request_id: str = "",  # [v4.2]
    is_admin: bool = False,  # [v4.2]
    mode: ConversationMode = ConversationMode.NATURAL # [v4.0]
) -> AsyncGenerator[str, None]:
    """
    [v3.2 Refactored] stream_message 오케스트레이션 (<= 200줄)
    """
    # ===== 초기화 =====
    session_id = thread_id or str(uuid.uuid4())
    user_id = user.id if user else "system"
    
    ctx = StreamContext(
        session_id=session_id,
        project_id=project_id or "system-master",
        thread_id=thread_id,
        user_id=user_id,
        user_input_raw=message,
        request_id=request_id,  # [v4.2]
        is_admin=is_admin,      # [v4.2]
        mode=mode               # [v4.0]
    )
    
    ctx.add_log("stream_message", f"=== v3.2 stream_message started (Mode: {mode}) ===")
    
    # ===== Step 1: 입력 정규화 =====
    ctx = parse_user_input(ctx)
    
    # ===== Step 2: Intent 분류 (LLM 기반 맥락 판단) =====
    ctx = await classify_intent(ctx)
    
    # ===== [v4.0] Auto Mode Switch (Dual Trigger) =====
    # Backend Intelligence: Intent -> Mode
    new_mode = ctx.mode
    if ctx.primary_intent == MasterIntent.REQUIREMENT:
        new_mode = ConversationMode.REQUIREMENT
    elif ctx.primary_intent in [MasterIntent.FUNCTION_WRITE, MasterIntent.FUNCTION_READ]:
        new_mode = ConversationMode.FUNCTION
    
    # If mode changed, update context and flag it
    if new_mode != ctx.mode:
        ctx.add_log("mode_switch", f"Auto-switching mode: {ctx.mode} -> {new_mode}")
        ctx.mode = new_mode
        ctx.mode_switched = True
        
        # Yield Mode Switch Signal immediately
        import json
        signal = json.dumps({
            "type": "MODE_SWITCH",
            "mode": new_mode.value,
            "reason": f"Intent detected: {ctx.primary_intent}"
        })
        yield f"{signal}\n"
    
    # ===== Step 3: MES 및 Verification 상태 로드 =====
    ctx = await load_current_mes_and_state(ctx)
    
    # ===== Step 4: Shadow Draft 추출 (조건부) =====
    if ctx.primary_intent == "NATURAL" or "HAS_BRAINSTORM_SIGNAL" in ctx.flags:
        ctx = await extract_shadow_draft(ctx)
    
    # ===== Step 5: MES 동기화 (조건부) =====
    if ctx.primary_intent == "REQUIREMENT":
        ctx = await sync_mes_if_needed(ctx)
    
    # ===== Step 6: MES Hash 재계산 =====
    if ctx.mes:
        ctx.mes_hash = compute_mes_hash(ctx.mes)
    
    # ===== Step 7: FUNCTION_READ 처리 (조건부) =====
    if ctx.primary_intent == "FUNCTION_READ":
        ctx = await handle_function_read(ctx)
    
    # ===== Step 8: FUNCTION_WRITE Gate 평가 (조건부) =====
    if ctx.primary_intent == "FUNCTION_WRITE":
        ctx = await handle_function_write_gate(ctx)
    
    # ===== Step 9: Response Builder =====
    ctx = response_builder(ctx)
    
    # ===== [v3.2.1 FIX] NATURAL, TOPIC_SHIFT, REQUIREMENT intent일 때는 LLM 호출 (OPENROUTER 통일) =====
    if ctx.primary_intent in ["NATURAL", "TOPIC_SHIFT", "REQUIREMENT"]:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from app.core.config import settings
        from app.services.embedding_service import embedding_service
        from app.core.vector_store import PineconeClient
        from app.core.neo4j_client import neo4j_client
        from app.core.database import get_messages_from_rdb  # [FIX] 누락된 import 추가
        
        try:
            # [중요] OPENROUTER로 통일 (Provider 분기 금지)
            llm = ChatOpenAI(
                model="google/gemini-2.0-flash-001",  # Flash급 모델 사용
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.7,
            )
            
            # [신규] Vector DB 검색 (의미 기반 맥락)
            relevant_context = ""
            try:
                # 사용자 질문 임베딩 생성
                query_embedding = await embedding_service.generate_embedding(message)
                
                # Vector DB 검색 (대화 청크 + 지식 그래프)
                vector_client = PineconeClient()
                
                # 1. 지식 검색 (Priority)
                knowledge_results = await vector_client.query_vectors(
                    tenant_id=ctx.project_id,
                    vector=query_embedding,
                    top_k=3,
                    namespace="knowledge"
                )
                
                # 2. 대화 이력 검색 (Secondary)
                conversation_results = await vector_client.query_vectors(
                    tenant_id=ctx.project_id,
                    vector=query_embedding,
                    top_k=2,
                    filter_metadata={"source": "conversation"},
                    namespace="conversation"
                )
                
                vector_results = knowledge_results + conversation_results
                
                # [v4.2] Vector 결과를 DebugInfo에 저장
                if ctx.is_admin and vector_results:
                    debug_chunks = []
                    for idx, res in enumerate(vector_results):
                        meta = res.get("metadata", {})
                        
                        title_val = meta.get("title")
                        text_val = meta.get("text") or meta.get("summary", "(원문 없음)")
                        
                        # [v4.2 FIX] Fallback title from text if missing
                        if not title_val or title_val == "Untitled":
                            title_val = (text_val[:30] + "...") if text_val and len(text_val) > 1 else "No Title"

                        chunk = RetrievalChunk(
                            rank=idx + 1,
                            score=res.get("score", 0.0),
                            title=title_val,
                            text=text_val,
                            source_message_id=meta.get("source_message_id"),
                            node_id=meta.get("node_id"),  # [v5.0 Critical] Neo4j ID for tab navigation
                            type=meta.get("type", "Concept"),  # [v5.0] Node type for UI
                            metadata=meta
                        )
                        debug_chunks.append(chunk)
                    
                    ctx.debug_info.retrieval.chunks = debug_chunks
                
                # [v5.0 Critical Fix] Admin Debug Info 즉시 저장 (404 방지)
                if ctx.is_admin and ctx.request_id:
                    try:
                        await debug_service.save_debug_info(ctx.request_id, ctx.debug_info)
                        ctx.add_log("debug_cache", f"Debug info cached immediately for request {ctx.request_id}")
                    except Exception as e:
                        ctx.add_log("debug_cache", f"Failed to cache debug info: {e}")
                
                # 맥락 구성 (지식 우선)
                relevant_context = ""
                context_parts = []
                
                if knowledge_results:
                    context_parts.append("=== [지식 베이스] ===")
                    for i, res in enumerate(knowledge_results):
                        meta = res.get("metadata", {})
                        text = meta.get("text") or meta.get("summary", "")
                        context_parts.append(f"[{i+1}] (유사도: {res['score']:.2f}) {text}")
                        
                if conversation_results:
                    context_parts.append("\n=== [과거 대화] ===")
                    for i, res in enumerate(conversation_results):
                        meta = res.get("metadata", {})
                        text = meta.get("text") or meta.get("summary", "")
                        context_parts.append(f"[{i+1}] (유사도: {res['score']:.2f}) {text}")

                if context_parts:
                    relevant_context = "\n".join(context_parts)
                    ctx.add_log("vector_search", f"Found {len(knowledge_results)} knowledge chunks, {len(conversation_results)} chat chunks")
                    
                    # [Test Log] Proof of Knowledge Persistence (Requested by User)
                    print(f"DEBUG: [Knowledge Persistence] Project {ctx.project_id} - Loaded {len(knowledge_results)} Graph/Vector nodes for New Chat context.")
            except Exception as e:
                ctx.add_log("vector_search", f"Vector search failed: {e}")
                # Vector 검색 실패는 무시하고 계속 진행
            
            # [v3.2.1 FIX] 직전 대화 이력 로드 (최근 10개)
            recent_messages = await get_messages_from_rdb(
                project_id=ctx.project_id,
                thread_id=ctx.thread_id,
                limit=10
            )
            
            ctx.add_log("llm_context", f"Loaded {len(recent_messages)} recent messages for context")
            
            # 시스템 프롬프트 (intent별 차별화)
            if ctx.primary_intent == "REQUIREMENT":
                # REQUIREMENT: MES 정보 포함
                agents_count = len(ctx.mes.get("agents", []))
                mes_info = f"현재 프로젝트에는 {agents_count}개의 에이전트가 등록되어 있습니다." if agents_count > 0 else "아직 에이전트가 등록되지 않았습니다."
                
                # Vector Context 추가
                vector_context_str = ""
                if relevant_context:
                    vector_context_str = f"\n[Context Identified]\n[관련 지식/대화]\n{relevant_context}\n"
                    print(f"DEBUG: [RAG Injection] Injected {len(relevant_context)} chars of context into System Prompt.")
                
                system_prompt = f"""당신은 프로젝트 관리를 돕는 AI 어시스턴트입니다.

[현재 프로젝트 상태]
{mes_info}
{vector_context_str}

사용자의 요구사항을 이해하고 다음 단계를 안내하세요:
- 프로젝트를 만들고 싶다면: 프로젝트 생성 절차 안내
- 에이전트를 추가하고 싶다면: 에이전트 추가 방법 안내
- 설정을 변경하고 싶다면: 설정 변경 방법 안내

호칭은 '사용자님'을 사용하세요.
자연스럽고 도움이 되는 답변을 제공하세요.
START TASK, READY_TO_START 같은 시스템 메시지는 출력하지 마세요."""
            else:
                # NATURAL/TOPIC_SHIFT: 일반 대화
                vector_context_str = ""
                if relevant_context:
                    vector_context_str = f"\n[Context Identified]\n[관련 지식/대화]\n{relevant_context}\n위 관련 정보를 참고하되, 최신 대화 맥락을 우선하세요.\n"
                    print(f"DEBUG: [RAG Injection] Injected {len(relevant_context)} chars of context into System Prompt.")
                
                system_prompt = f"""당신은 친절한 AI 어시스턴트입니다.
{vector_context_str}
사용자와 자연스럽게 대화하세요.
이전 대화 맥락을 기억하고 연속된 대화를 이어가세요.
호칭은 '사용자님'을 사용하세요.
짧고 간결하게 답변하세요.
운영 메뉴나 명령어 안내는 하지 마세요.
START TASK, READY_TO_START, MISSION READINESS 같은 시스템 메시지는 절대 출력하지 마세요."""
            
            # LLM 메시지 구성 (이전 대화 포함)
            messages = [SystemMessage(content=system_prompt)]
            
            # 최근 대화 이력 추가 (최대 10개)
            for msg in recent_messages[-10:]:
                if msg.sender_role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.sender_role == "assistant":
                    messages.append(AIMessage(content=msg.content))
            
            # 현재 사용자 메시지 추가
            messages.append(HumanMessage(content=message))
            
            ctx.add_log("llm_context", f"Sending {len(messages)} messages to LLM (including {len(recent_messages)} history)")
            
            response = await llm.ainvoke(messages)
            ctx.final_response = response.content
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            ctx.add_log("stream_message", f"LLM error: {e}\n{error_trace}")
            print(f"CRITICAL LLM ERROR: {e}\n{error_trace}") # 콘솔에도 강제 출력
            ctx.final_response = "죄송합니다. 시스템 오류가 발생하여 요청을 처리할 수 없습니다. 관리자에게 문의해주세요."
    
    # ===== Step 10: 최종 응답 후처리 (모든 intent에 대해 1회만) =====
    ctx.final_response = _clean_response_final(ctx.final_response, ctx.primary_intent, ctx.write_gate_open)
    
    # ===== Step 11: 상태 저장 (persist_state) =====
    # [TODO] MES/Hash/Draft/verification_state를 Redis/DB에 저장
    # 지금은 메시지만 저장
    # [v4.2 Update] 사용자 메시지 저장 및 Knowledge Queue 등록
    user_msg_id, saved_thread_id = await save_message_to_rdb("user", message, project_id, thread_id, metadata={"user_id": user_id})
    
    # [KNOW-001] Knowledge Ingestion Trigger
    # 사용자의 메시지를 지식 큐에 등록하여 비동기로 처리 (중요도 필터링은 worker가 수행)
    try:
        if user_msg_id:
            knowledge_queue.put_nowait(user_msg_id)
            ctx.add_log("knowledge_ingestion", f"Message {user_msg_id} queued for knowledge processing")
    except Exception as e:
        ctx.add_log("knowledge_ingestion", f"Failed to queue message: {e}")

    asst_msg_id, _ = await save_message_to_rdb(
        "assistant", 
        ctx.final_response, 
        project_id, 
        thread_id,
        metadata={"request_id": ctx.request_id} if ctx.request_id else None # [v4.2] Save Request ID
    )
    
    # [v4.0] Auto-Ingestion for Requirement Mode (Assistant Response)
    if ctx.mode == ConversationMode.REQUIREMENT and asst_msg_id:
        try:
            knowledge_queue.put_nowait(asst_msg_id)
            ctx.add_log("knowledge_ingestion", f"Auto-ingesting Assistant Response {asst_msg_id} (Requirement Mode)")
        except Exception as e:
            ctx.add_log("knowledge_ingestion", f"Failed to auto-ingest assistant response: {e}")
    


    # [v4.2] Admin인 경우 Debug Info 캐싱 (TTL 10분)
    if ctx.is_admin and ctx.request_id:
        await debug_service.save_debug_info(ctx.request_id, ctx.debug_info)
    
    ctx.add_log("stream_message", "=== v3.2 stream_message completed ===")
    
    # ===== 최종 응답 스트리밍 =====
    
    # [v5.0] Admin 출처 호출 (Source Auditing)
    # 메시지 끝에 구분자와 함께 request_id를 메타데이터 형태로 전달하지 않고
    # 프론트엔드에서는 이미 응답 헤더의 X-Request-Id 또는 저장된 메시지의 metadata_json을 통해 확인하고 있습니다.
    # 하지만 사용자가 "출처 라인 호출"을 명시적으로 요청했으므로, 
    # 어드민인 경우 응답 끝에 보이지 않는 메타데이터나 특정 시그널을 추가할 수 있습니다.
    # 현재 프론트엔드(ChatInterface.tsx)는 msg.request_id가 있으면 자동으로 출처 바를 렌더링합니다.
    # 따라서 여기서 별도의 텍스트를 추가할 필요는 없지만, 확실한 동작을 위해 로그만 남깁니다.
    
    yield ctx.final_response
    yield "\n" # Ensure clean end


def _clean_response_final(content: str, intent: str, gate_open: bool) -> str:
    """
    [v3.2] 최종 응답 후처리 (모든 intent에 대해 1회만)
    
    제거 대상:
    - MISSION READINESS REPORT
    - READY_TO_START JSON (FUNCTION_WRITE + Gate Open이 아닌 경우)
    - 설정 오류 블록
    """
    import re
    
    # [Guardrail] FUNCTION_WRITE + Gate Open이 아니면 READY_TO_START 제거
    if intent != "FUNCTION_WRITE" or not gate_open:
        patterns = [
            # MISSION READINESS REPORT
            r"---\s*MISSION READINESS REPORT\s*---[\s\S]*?(?=\n\n|\Z)",
            r"\[준비 상태 점검 완료\][\s\S]*?(?=\n\n|\Z)",
            
            # READY_TO_START JSON
            r'```json\s*\{\s*"status"\s*:\s*"READY_TO_START"[\s\S]*?```',
            r'\{\s*"status"\s*:\s*"READY_TO_START"[\s\S]*?\}',
            
            # 조치 방법 가이드
            r"## 조치 방법 가이드[\s\S]*?(?=\n\n|\Z)",
            r"\*\*권장 조치:\*\*[\s\S]*?(?=\n\n|\Z)",
        ]
        
        for pattern in patterns:
            content = re.sub(pattern, "", content, flags=re.MULTILINE | re.DOTALL)
    
    # 연속 빈 줄 제거
    content = re.sub(r"\n{3,}", "\n\n", content)
    
    return content.strip()

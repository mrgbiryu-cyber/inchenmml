# -*- coding: utf-8 -*-
import json
import sys

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
from app.models.master import MasterAgentConfig, ChatRequest, ChatResponse, ChatMessage
from app.services.master_agent_service import MasterAgentService
from app.api.dependencies import get_current_user
from app.models.schemas import User

router = APIRouter()
service = MasterAgentService()

@router.get("/config", response_model=MasterAgentConfig)
async def get_config():
    """Get current master agent configuration"""
    return service.get_config()

@router.post("/config", response_model=MasterAgentConfig)
async def update_config(config: MasterAgentConfig):
    """Update master agent configuration"""
    print(f"DEBUG: Updating Master Config with Provider: {config.provider}, Model: {config.model}")
    service.update_config(config)
    return service.get_config()

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Send a message to the master agent (REST API - non-streaming).
    """
    print(f"DEBUG: Chat endpoint received project_id: {request.project_id} from User: {current_user.username}")
    
    response = await service.process_message(
        request.message, 
        request.history, 
        request.project_id, 
        request.thread_id,
        user=current_user,
        worker_status=request.worker_status
    )
    return ChatResponse(
        message=response["message"],
        quick_links=response["quick_links"]
    )

@router.post("/chat-stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    [TODO 8] Streaming chat with Tool Call Interceptor.
    """
    async def event_generator():
        try:
            async for chunk in service.stream_message(
                request.message, 
                request.history, 
                request.project_id, 
                request.thread_id,
                user=current_user,
                worker_status=request.worker_status
            ):
                # Send as simple text chunks or JSON if needed. 
                # For basic streaming, we send raw text.
                yield chunk
        except Exception as e:
            yield f"\n[Error]: {str(e)}"

    return StreamingResponse(event_generator(), media_type="text/plain")

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    Real-time chat with the master agent.
    """
    await websocket.accept()
    history = []
    
    try:
        while True:
            data = await websocket.receive_text()
            request = json.loads(data)
            action = request.get("action")
            
            if action == "start_task":
                # Trigger job creation
                # We need OrchestrationService and User
                # For prototype, we'll use a mock user or the one from auth (if we had auth on WS)
                # Since WS doesn't have auth middleware here yet, we'll mock the user.
                # TODO: Implement proper WS auth.
                from app.models.schemas import User
                mock_user = User(
                    id="user_admin_001", 
                    username="admin", 
                    email="admin@buja.ai", 
                    role="super_admin", 
                    tenant_id="tenant_hyungnim"
                )
                
                # Get OrchestrationService
                job_manager = websocket.app.state.job_manager
                redis_client = websocket.app.state.redis
                from app.services.orchestration_service import OrchestrationService
                orchestrator = OrchestrationService(job_manager, redis_client)
                
                response = await service.create_job_from_history(history, orchestrator, mock_user)
                
                # Update history
                history.append(ChatMessage(role="assistant", content=response["message"]))
                
                await websocket.send_json({
                    "message": response["message"],
                    "quick_links": [] # Could add link to execution page
                })
                
            else:
                user_message = request.get("message")
                
                # Update history
                history.append(ChatMessage(role="user", content=user_message))
                
                # Process message
                response = await service.process_message(user_message, history)
                
                # Update history with response
                history.append(ChatMessage(role="assistant", content=response["message"]))
                
                # Send response
                await websocket.send_json({
                    "message": response["message"],
                    "quick_links": response["quick_links"]
                })
            
    except WebSocketDisconnect:
        print("Master chat disconnected")
    except Exception as e:
        print(f"Master chat error: {e}")
        await websocket.close()

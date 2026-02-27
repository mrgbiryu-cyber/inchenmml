# -*- coding: utf-8 -*-
import asyncio
import sys

# [UTF-8] Force stdout/stderr to UTF-8
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from structlog import get_logger
from redis.asyncio import Redis

router = APIRouter()
logger = get_logger(__name__)

@router.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """
    WebSocket endpoint for streaming orchestration events.
    Subscribes to Redis channel `orchestration:{project_id}`.
    """
    await websocket.accept()
    
    # Get Redis from app state
    redis_client: Redis = websocket.app.state.redis
    pubsub = redis_client.pubsub()
    channel_name = f"orchestration:{project_id}"
    
    await pubsub.subscribe(channel_name)
    logger.info(f"WebSocket connected for project {project_id}, subscribed to {channel_name}")
    
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                # Forward Redis message to WebSocket
                data = message["data"]
                # Ensure data is string
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                
                await websocket.send_text(data)
            
            # Keep connection alive and check for client disconnect
            # We can send a ping or just rely on get_message timeout loop
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for project {project_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()

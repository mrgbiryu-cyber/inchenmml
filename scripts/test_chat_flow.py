import asyncio
import os
import sys
from typing import AsyncGenerator

# 프로젝트 루트를 path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.v32_stream_message_refactored import stream_message_v32
from app.models.schemas import User

# 더미 유저 생성
dummy_user = User(
    id="test-user-id",
    username="testuser",
    email="test@example.com",
    role="standard_user",
    tenant_id="test-tenant"
)

async def test_chat():
    print("=== Chat Flow Test Start ===")
    
    # 테스트 메시지
    message = "안녕"
    history = [] # 빈 히스토리
    
    print(f"Input Message: {message}")
    
    try:
        print("Stream Output:")
        async for chunk in stream_message_v32(
            message=message,
            history=history,
            project_id="test-project",
            thread_id="test-thread",
            user=dummy_user
        ):
            print(chunk, end="", flush=True)
        print("\n=== Chat Flow Test End ===")
        
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat())

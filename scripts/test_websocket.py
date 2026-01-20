import asyncio
import websockets
import json
import redis.asyncio as redis

async def test_websocket():
    project_id = "test-project-123"
    root_health_url = "http://localhost:8002/health"
    http_url = "http://localhost:8002/api/v1/orchestration/health"
    uri = f"ws://localhost:8002/api/v1/orchestration/ws/{project_id}"
    redis_url = "redis://localhost:6379/0"

    # 0. Check Root Health
    import httpx
    try:
        print(f"🔍 Checking Root Health: {root_health_url}")
        resp = httpx.get(root_health_url)
        print(f"   Root Health Status: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Root Health Check Failed: {e}")

    # 1. Check HTTP
    import httpx
    try:
        print(f"🔍 Checking HTTP: {http_url}")
        resp = httpx.get(http_url)
        print(f"   HTTP Status: {resp.status_code}")
        print(f"   HTTP Body: {resp.json()}")
    except Exception as e:
        print(f"   ❌ HTTP Check Failed: {e}")

    print(f"🔌 Connecting to WebSocket: {uri}")
    
    try:
        # Add Origin header to mimic browser
        async with websockets.connect(uri, origin="http://localhost:3000") as websocket:
            print("   ✅ WebSocket Connected")
            
            # Simulate backend publishing an event via Redis
            print("   📢 Publishing test event to Redis...")
            r = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            channel = f"orchestration:{project_id}"
            test_message = {
                "type": "TEST_EVENT",
                "data": {"message": "Hello WebSocket"},
                "timestamp": 1234567890
            }
            await r.publish(channel, json.dumps(test_message))
            await r.close()
            
            # Wait for message
            print("   👂 Waiting for message...")
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"   📩 Received: {response}")
            
            data = json.loads(response)
            if data["type"] == "TEST_EVENT" and data["data"]["message"] == "Hello WebSocket":
                print("   ✅ Verification Successful: Redis -> WebSocket -> Client works!")
            else:
                print("   ❌ Verification Failed: Content mismatch")
                
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())

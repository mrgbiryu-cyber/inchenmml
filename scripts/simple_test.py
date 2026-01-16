"""
Simple job creation test
"""
import asyncio
import httpx

async def test():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login
        print("1. Logging in...")
        login_resp = await client.post(
            "http://localhost:8000/api/v1/auth/token",
            json={"username": "admin", "password": "admin123"}
        )
        print(f"   Login status: {login_resp.status_code}")
        
        if login_resp.status_code != 200:
            print(f"   Error: {login_resp.text}")
            return
        
        token = login_resp.json()["access_token"]
        print(f"   ✅ Token received")
        
        # Create job
        print("\n2. Creating job...")
        job_resp = await client.post(
            "http://localhost:8000/api/v1/jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "execution_location": "LOCAL_MACHINE",
                "provider": "OLLAMA",
                "model": "test-model",
                "timeout_sec": 60,
                "repo_root": "C:/temp/test",
                "allowed_paths": [""]
            }
        )
        
        print(f"   Job creation status: {job_resp.status_code}")
        print(f"   Response: {job_resp.text}")

asyncio.run(test())

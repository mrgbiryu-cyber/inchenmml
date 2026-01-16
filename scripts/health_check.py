"""
Health check script for BUJA Core Platform
Verifies all services are running and accessible
"""
import asyncio
import httpx
import sys


async def check_backend():
    """Check if backend is running"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8000/health",
                timeout=5.0
            )
            
            if response.status_code == 200:
                health = response.json()
                print("✅ Backend: Running")
                print(f"   Status: {health.get('status')}")
                print(f"   Redis: {health.get('components', {}).get('redis')}")
                return True
            else:
                print(f"⚠️  Backend: Unhealthy (status {response.status_code})")
                return False
                
    except Exception as e:
        print(f"❌ Backend: Not accessible ({e})")
        return False


async def check_redis():
    """Check if Redis is accessible via backend"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8000/health",
                timeout=5.0
            )
            
            if response.status_code == 200:
                health = response.json()
                redis_status = health.get('components', {}).get('redis')
                
                if redis_status == 'healthy':
                    print("✅ Redis: Accessible")
                    return True
                else:
                    print(f"⚠️  Redis: {redis_status}")
                    return False
            else:
                print("❌ Redis: Cannot check (backend unhealthy)")
                return False
                
    except Exception as e:
        print(f"❌ Redis: Cannot check ({e})")
        return False


async def check_auth():
    """Check if authentication works"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/v1/auth/token",
                json={
                    "username": "admin",
                    "password": "admin123"
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                print("✅ Authentication: Working")
                return True
            else:
                print(f"⚠️  Authentication: Failed (status {response.status_code})")
                return False
                
    except Exception as e:
        print(f"❌ Authentication: Not accessible ({e})")
        return False


async def main():
    """Run all health checks"""
    print("=" * 70)
    print("BUJA Core Platform - Health Check")
    print("=" * 70)
    print()
    
    results = []
    
    # Check backend
    print("Checking Backend...")
    results.append(await check_backend())
    print()
    
    # Check Redis
    print("Checking Redis...")
    results.append(await check_redis())
    print()
    
    # Check authentication
    print("Checking Authentication...")
    results.append(await check_auth())
    print()
    
    # Summary
    print("=" * 70)
    if all(results):
        print("✅ All systems operational!")
        print("=" * 70)
        print()
        print("You can now:")
        print("1. Start the worker: python -m local_agent_hub.main")
        print("2. Run integration test: python scripts/test_job.py")
        sys.exit(0)
    else:
        print("⚠️  Some systems are not ready")
        print("=" * 70)
        print()
        print("Troubleshooting:")
        print("1. Start Redis: cd docker && docker-compose up -d redis")
        print("2. Start Backend: cd backend && python -m app.main")
        print("3. Check logs for errors")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

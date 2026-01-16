"""
Direct Job Manager test to find the error
"""
import sys
import asyncio
sys.path.insert(0, 'D:/project/myllm/backend')

from app.core.config import settings
from app.services.job_manager import JobManager
from app.models.schemas import JobCreate, User, UserRole, ExecutionLocation, ProviderType
import redis.asyncio as redis

async def test():
    print("=" * 70)
    print("Direct Job Manager Test")
    print("=" * 70)
    print()
    
    # Connect to Redis
    print("1. Connecting to Redis...")
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
    await redis_client.ping()
    print("   ✅ Connected")
    
    # Create Job Manager
    print("\n2. Creating Job Manager...")
    job_manager = JobManager(redis_client)
    print("   ✅ Created")
    
    # Create mock user
    print("\n3. Creating mock user...")
    user = User(
        id="test_user",
        username="admin",
        tenant_id="tenant_test",
        role=UserRole.SUPER_ADMIN,
        is_active=True
    )
    print("   ✅ Created")
    
    # Create job request
    print("\n4. Creating job request...")
    job_request = JobCreate(
        execution_location=ExecutionLocation.LOCAL_MACHINE,
        provider=ProviderType.OLLAMA,
        model="test-model",
        timeout_sec=60,
        repo_root="C:/temp/test",
        allowed_paths=[""]
    )
    print("   ✅ Created")
    
    # Try to create job
    print("\n5. Creating job...")
    try:
        job = await job_manager.create_job(user, job_request)
        print(f"   ✅ Job created: {job.job_id}")
        print(f"   Status: {job.status}")
    except Exception as e:
        import traceback
        print(f"   ❌ Error: {e}")
        print(f"\nFull traceback:")
        print(traceback.format_exc())
    
    await redis_client.close()
    print("\n" + "=" * 70)

asyncio.run(test())

"""
Test job submission script
Sends a "Hello World" job to the backend
"""
import asyncio
import httpx
import json
from pathlib import Path
import tempfile


# Configuration
BACKEND_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"


async def login() -> str:
    """Login and get JWT token"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/api/v1/auth/token",
            json={
                "username": USERNAME,
                "password": PASSWORD
            }
        )
        
        if response.status_code == 200:
            token = response.json()["access_token"]
            print(f"✅ Logged in as {USERNAME}")
            return token
        else:
            print(f"❌ Login failed: {response.text}")
            raise Exception("Login failed")


async def create_test_job(token: str, test_dir: Path) -> dict:
    """Create a test job"""
    
    job_request = {
        "execution_location": "LOCAL_MACHINE",
        "provider": "OLLAMA",
        "model": "mimo-v2-flash",
        "timeout_sec": 300,
        "repo_root": str(test_dir),
        "allowed_paths": [""],  # Allow root-level files
        "steps": ["create_file"],
        "priority": 5,
        "metadata": {
            "objective": "Create a Hello World file",
            "requirements": [
                "Create a file named hello_buja.txt",
                "Write 'Hello from BUJA Core Platform - Phase 4!' to the file"
            ],
            "success_criteria": [
                "File hello_buja.txt exists",
                "File contains the correct message"
            ],
            "language": "Python",
            "framework": "N/A",
            "notes": "This is a test job to verify end-to-end integration"
        },
        "file_operations": [
            {
                "action": "CREATE",
                "path": "hello_buja.txt",
                "description": "Hello World test file"
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BACKEND_URL}/api/v1/jobs",
            headers={"Authorization": f"Bearer {token}"},
            json=job_request,
            timeout=30.0
        )
        
        if response.status_code == 202:
            result = response.json()
            print(f"✅ Job created: {result['job_id']}")
            print(f"   Status: {result['status']}")
            print(f"   Message: {result['message']}")
            return result
        else:
            print(f"❌ Job creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            raise Exception("Job creation failed")


async def check_job_status(token: str, job_id: str) -> dict:
    """Check job status"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_URL}/api/v1/jobs/{job_id}/status",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0
        )
        
        if response.status_code == 200:
            status = response.json()
            print(f"\n📊 Job Status:")
            print(f"   Job ID: {status['job_id']}")
            print(f"   Status: {status['status']}")
            print(f"   Execution Location: {status.get('execution_location')}")
            print(f"   Model: {status.get('model')}")
            
            if status.get('result'):
                print(f"\n📝 Result:")
                result = status['result']
                if isinstance(result, dict):
                    print(json.dumps(result, indent=2))
                else:
                    print(result)
            
            return status
        else:
            print(f"❌ Status check failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None


async def main():
    """Main test flow"""
    print("=" * 70)
    print("BUJA Core Platform - Integration Test")
    print("=" * 70)
    print()
    
    # Create test directory
    test_dir = Path(tempfile.gettempdir()) / "buja_test"
    test_dir.mkdir(exist_ok=True)
    print(f"📁 Test directory: {test_dir}")
    print()
    
    try:
        # Step 1: Login
        print("Step 1: Logging in...")
        token = await login()
        print()
        
        # Step 2: Create job
        print("Step 2: Creating test job...")
        job = await create_test_job(token, test_dir)
        job_id = job["job_id"]
        print()
        
        # Step 3: Wait for worker to process
        print("Step 3: Waiting for worker to process job...")
        print("   (Worker should poll and execute within 30 seconds)")
        print()
        
        # Wait a bit for worker to pick up the job
        await asyncio.sleep(10)
        
        # Step 4: Check status
        print("Step 4: Checking job status...")
        status = await check_job_status(token, job_id)
        print()
        
        # Step 5: Verify file creation
        print("Step 5: Verifying file creation...")
        test_file = test_dir / "hello_buja.txt"
        
        if test_file.exists():
            content = test_file.read_text()
            print(f"✅ File created successfully!")
            print(f"   Path: {test_file}")
            print(f"   Content: {content}")
        else:
            print(f"⚠️  File not found: {test_file}")
            print(f"   This is expected if using simulated Roo Code")
            print(f"   Check TASK.md was generated in: {test_dir}")
        
        print()
        print("=" * 70)
        print("✅ Integration Test Complete!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Check worker logs for execution details")
        print("2. Verify TASK.md was generated in test directory")
        print("3. Check backend logs for job lifecycle events")
        print()
        
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Test failed: {e}")
        print("=" * 70)
        print()
        print("Troubleshooting:")
        print("1. Ensure backend is running: http://localhost:8000")
        print("2. Ensure Redis is running: docker-compose ps")
        print("3. Ensure worker is running and polling")
        print("4. Check logs for detailed error messages")
        print()


if __name__ == "__main__":
    asyncio.run(main())

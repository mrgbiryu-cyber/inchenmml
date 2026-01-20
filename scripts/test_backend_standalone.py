import sys
import os
from fastapi.testclient import TestClient

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.main import app

def test_backend():
    print("🚀 Testing Backend Standalone (TestClient)")
    with TestClient(app) as client:
        # 1. Check Root Health
        print("1. Checking Root Health...")
        resp = client.get("/health")
    if resp.status_code == 200:
        print("   ✅ Root Health: OK")
    else:
        print(f"   ❌ Root Health Failed: {resp.status_code}")

    # 2. Check Orchestration Health
    print("\n2. Checking Orchestration Health...")
    resp = client.get("/api/v1/orchestration/health")
    if resp.status_code == 200:
        print("   ✅ Orchestration Health: OK")
    else:
        print(f"   ❌ Orchestration Health Failed: {resp.status_code}")

    # 3. Check WebSocket
    print("\n3. Checking WebSocket...")
    project_id = "test-project-123"
    try:
        with client.websocket_connect(f"/api/v1/orchestration/ws/{project_id}") as websocket:
            print("   ✅ WebSocket Connected")
            # We can't easily test Redis Pub/Sub here without a real Redis and async loop in TestClient sync mode
            # But connecting proves the endpoint exists and accepts connections.
    except Exception as e:
        print(f"   ❌ WebSocket Failed: {e}")

if __name__ == "__main__":
    test_backend()

import requests
import sys
import time
import json

BASE_URL = "http://localhost:8002/api/v1"

def login(username, password):
    response = requests.post(f"{BASE_URL}/auth/token", json={"username": username, "password": password})
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.text}")
        sys.exit(1)

def test_orchestration():
    print("🚀 Testing Orchestration Service")
    print("============================================================")
    
    # 1. Login
    print("1. Logging in as User (user1)...")
    token = login("user1", "user123")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Create Project
    print("2. Creating new project...")
    project_data = {
        "id": "orch-test",
        "name": "Orchestration Test Project",
        "description": "Testing LangGraph execution",
        "project_type": "NEW",
        "tenant_id": "ignored",
        "user_id": "ignored"
    }
    response = requests.post(f"{BASE_URL}/projects/", json=project_data, headers=headers)
    if response.status_code == 201:
        project_id = response.json()["id"]
        print(f"   ✅ Created Project ID: {project_id}")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        sys.exit(1)
        
    # 3. Save Agent Config
    print("3. Configuring Agents...")
    agent_config = {
        "workflow_type": "SEQUENTIAL",
        "entry_agent_id": "planner",
        "agents": [
            {
                "agent_id": "planner",
                "role": "PLANNER",
                "model": "gpt-4",
                "provider": "OPENROUTER",
                "system_prompt": "Plan the task.",
                "next_agents": ["coder"]
            },
            {
                "agent_id": "coder",
                "role": "CODER",
                "model": "claude-3-opus",
                "provider": "OPENROUTER",
                "system_prompt": "Write the code.",
                "next_agents": []
            }
        ]
    }
    response = requests.post(f"{BASE_URL}/projects/{project_id}/agents", json=agent_config, headers=headers)
    if response.status_code == 200:
        print("   ✅ Agent config saved")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        sys.exit(1)
        
    # 4. Execute Workflow
    print("4. Triggering Execution...")
    response = requests.post(f"{BASE_URL}/projects/{project_id}/execute", headers=headers)
    if response.status_code == 202:
        print("   ✅ Workflow started")
        execution_id = response.json().get("execution_id")
        print(f"   🆔 Execution ID: {execution_id}")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        sys.exit(1)
        
    # 5. Monitor (Simulated)
    print("5. Monitoring (Check backend logs for 'Executing Agent')...")
    # Since we don't have a status endpoint for the workflow itself yet (only jobs),
    # we'll just wait a bit. In a real test, we'd poll the job status or workflow status.
    time.sleep(5)
    print("   ✅ Test finished (Check logs for async execution details)")

if __name__ == "__main__":
    test_orchestration()

import requests
import sys
import json

BASE_URL = "http://localhost:8002/api/v1"

def login(username, password):
    response = requests.post(f"{BASE_URL}/auth/token", json={"username": username, "password": password})
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.text}")
        sys.exit(1)

def test_projects_crud():
    print("🔒 Testing Projects API")
    print("============================================================")
    
    # 1. Login
    print("1. Logging in as User (user1)...")
    token = login("user1", "user123")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Create Project
    print("2. Creating new project...")
    project_data = {
        "id": "temp-id", # Will be ignored/overwritten by backend
        "name": "My AI Project",
        "description": "A test project",
        "project_type": "NEW",
        "tenant_id": "ignored",
        "user_id": "ignored"
    }
    response = requests.post(f"{BASE_URL}/projects/", json=project_data, headers=headers)
    if response.status_code == 201:
        project = response.json()
        project_id = project["id"]
        print(f"   ✅ Created Project ID: {project_id}")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        sys.exit(1)
        
    # 3. List Projects
    print("3. Listing projects...")
    response = requests.get(f"{BASE_URL}/projects/", headers=headers)
    if response.status_code == 200:
        projects = response.json()
        print(f"   ✅ Found {len(projects)} projects")
        if not any(p["id"] == project_id for p in projects):
            print("   ❌ Created project not found in list")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        
    # 4. Get Project Detail
    print(f"4. Getting project details for {project_id}...")
    response = requests.get(f"{BASE_URL}/projects/{project_id}", headers=headers)
    if response.status_code == 200:
        print("   ✅ Success")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        
    # 5. Update Project
    print("5. Updating project description...")
    update_data = {"description": "Updated description"}
    response = requests.patch(f"{BASE_URL}/projects/{project_id}", json=update_data, headers=headers)
    if response.status_code == 200:
        if response.json()["description"] == "Updated description":
            print("   ✅ Update successful")
        else:
            print("   ❌ Update failed (value mismatch)")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        
    # 6. Save Agent Config
    print("6. Saving Agent Config...")
    agent_config = {
        "workflow_type": "SEQUENTIAL",
        "entry_agent_id": "planner",
        "agents": [
            {
                "agent_id": "planner",
                "role": "PLANNER",
                "model": "gpt-4",
                "provider": "OPENROUTER",
                "system_prompt": "You are a planner.",
                "next_agents": ["coder"]
            },
            {
                "agent_id": "coder",
                "role": "CODER",
                "model": "claude-3",
                "provider": "OPENROUTER",
                "system_prompt": "You are a coder.",
                "next_agents": []
            }
        ]
    }
    response = requests.post(f"{BASE_URL}/projects/{project_id}/agents", json=agent_config, headers=headers)
    if response.status_code == 200:
        print("   ✅ Agent config saved")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        
    # 7. Get Agent Config
    print("7. Getting Agent Config...")
    response = requests.get(f"{BASE_URL}/projects/{project_id}/agents", headers=headers)
    if response.status_code == 200:
        print("   ✅ Agent config retrieved")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")

    # 8. Delete Project
    print("8. Deleting project...")
    response = requests.delete(f"{BASE_URL}/projects/{project_id}", headers=headers)
    if response.status_code == 204:
        print("   ✅ Deleted successfully")
    else:
        print(f"   ❌ Failed: {response.status_code} - {response.text}")
        
    print("============================================================")

if __name__ == "__main__":
    test_projects_crud()

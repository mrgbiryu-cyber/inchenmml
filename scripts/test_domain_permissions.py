import requests
import sys

BASE_URL = "http://localhost:8002/api/v1"

def login(username, password):
    response = requests.post(f"{BASE_URL}/auth/token", json={"username": username, "password": password})
    if response.status_code != 200:
        print(f"Login failed for {username}: {response.text}")
        sys.exit(1)
    return response.json()["access_token"]

def create_job(token, repo_root):
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "execution_location": "LOCAL_MACHINE",
        "provider": "OLLAMA",
        "model": "mimo-v2-flash",
        "repo_root": repo_root,
        "allowed_paths": ["src/"],
        "metadata": {"objective": "Test permission"}
    }
    response = requests.post(f"{BASE_URL}/jobs", json=data, headers=headers)
    return response

def main():
    print("🔒 Testing Domain Permissions")
    print("============================================================")

    # 1. Login as Admin to setup
    print("1. Logging in as Admin...")
    admin_token = login("admin", "admin123")
    
    # 2. Create a restricted user (or use existing user1)
    # We'll use user1 who is a STANDARD_USER
    print("2. Logging in as Standard User (user1)...")
    user_token = login("user1", "user123")

    # 3. Setup: Grant user1 access to a specific domain
    print("3. [Admin] Granting user1 access to '/allowed/project'...")
    # First create the domain
    requests.post(f"{BASE_URL}/admin/domains", json={
        "id": "project-allowed",
        "name": "Allowed Project",
        "repo_root": "/allowed/project",
        "owner_id": "admin"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    
    # Grant access
    requests.post(f"{BASE_URL}/admin/users/user_001/domains", params={"domain_id": "/allowed/project"}, headers={"Authorization": f"Bearer {admin_token}"})
    
    # 4. Test: Try to create job in ALLOWED path
    print("4. [User] Creating job in '/allowed/project' (Should SUCCESS)...")
    res = create_job(user_token, "/allowed/project")
    if res.status_code == 202:
        print("   ✅ Success (202 Accepted)")
    else:
        print(f"   ❌ Failed: {res.status_code} - {res.text}")

    # 5. Test: Try to create job in FORBIDDEN path
    print("5. [User] Creating job in '/forbidden/project' (Should FAIL)...")
    res = create_job(user_token, "/forbidden/project")
    if res.status_code == 403:
        print("   ✅ Correctly blocked (403 Forbidden)")
    else:
        print(f"   ❌ Failed to block: {res.status_code} - {res.text}")

    print("============================================================")

if __name__ == "__main__":
    main()

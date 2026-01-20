import asyncio
import json
import websockets
import sys
import os
from fastapi.testclient import TestClient

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.main import app

def test_master_agent_rest():
    print("🚀 Testing Master Agent (REST API)")
    with TestClient(app) as client:
        # 1. Get Config
        print("1. Getting Config...")
        resp = client.get("/api/v1/master/config")
        if resp.status_code == 200:
            print(f"   ✅ Config: {resp.json()}")
        else:
            print(f"   ❌ Config Failed: {resp.status_code}")

        # 2. Update Config
        print("\n2. Updating Config...")
        new_config = {
            "model": "gpt-3.5-turbo",
            "provider": "OPENROUTER",
            "system_prompt": "You are a test agent.",
            "temperature": 0.5
        }
        resp = client.post("/api/v1/master/config", json=new_config)
        if resp.status_code == 200 and resp.json()["model"] == "gpt-3.5-turbo":
            print("   ✅ Config Updated")
        else:
            print(f"   ❌ Update Failed: {resp.status_code}")

def test_master_agent_ws():
    print("\n🚀 Testing Master Agent (WebSocket via TestClient)")
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/api/v1/master/ws/chat") as websocket:
                print("   ✅ WebSocket Connected")
                
                # Send Message
                msg = {"message": "List all projects"}
                print(f"   📤 Sending: {msg}")
                websocket.send_json(msg)
                
                # Receive Response
                print("   👂 Waiting for response...")
                data = websocket.receive_json()
                
                print(f"   📩 Received: {str(data)[:100]}...")
                
                if "quick_links" in data:
                    print(f"   🔗 Quick Links: {len(data['quick_links'])}")
                    
        except Exception as e:
            print(f"   ❌ WebSocket Failed: {e}")

if __name__ == "__main__":
    test_master_agent_rest()
    test_master_agent_ws()


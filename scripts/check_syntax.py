import sys
import os

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    print("Checking app.api.v1.orchestration...")
    from app.api.v1 import orchestration
    print("✅ app.api.v1.orchestration imported successfully")
except Exception as e:
    print(f"❌ Failed to import app.api.v1.orchestration: {e}")

try:
    print("Checking app.main...")
    from app import main
    print("✅ app.main imported successfully")
except Exception as e:
    print(f"❌ Failed to import app.main: {e}")

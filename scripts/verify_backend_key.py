"""
Verify Backend Key Loading
Checks if the private key is loaded with correct newlines
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add backend to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'backend'))

# Load env
load_dotenv(project_root / 'backend' / '.env')

try:
    from app.core.config import settings
    from app.core.security import sign_job_payload
    
    print("=" * 70)
    print("Backend Key Loading Verification")
    print("=" * 70)
    print()
    
    # Check raw setting
    raw_key = settings.JOB_SIGNING_PRIVATE_KEY
    print(f"Raw Key Length: {len(raw_key)}")
    print(f"Has literal \\n: {'\\n' in raw_key}")
    print(f"Has actual newline: {'\n' in raw_key}")
    
    # Check if sign_job_payload handles it (we can't easily check internal var, 
    # but we can try to sign and see if it fails)
    
    print()
    print("Attempting to sign payload...")
    try:
        sig = sign_job_payload({"test": "data"})
        print(f"✅ Signing successful! Signature: {sig[:30]}...")
        print("   This means the key was correctly processed.")
    except Exception as e:
        print(f"❌ Signing failed: {e}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

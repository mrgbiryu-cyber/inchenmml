"""
Verify backend configuration
"""
import sys
sys.path.insert(0, 'D:/project/myllm/backend')

from app.core.config import settings

print("=" * 70)
print("Backend Configuration Verification")
print("=" * 70)
print()

# Check critical settings
checks = {
    "JWT_SECRET_KEY": settings.JWT_SECRET_KEY,
    "REDIS_URL": settings.REDIS_URL,
    "JOB_SIGNING_PRIVATE_KEY": settings.JOB_SIGNING_PRIVATE_KEY[:50] + "..." if settings.JOB_SIGNING_PRIVATE_KEY else None,
    "JOB_SIGNING_PUBLIC_KEY": settings.JOB_SIGNING_PUBLIC_KEY[:50] + "..." if settings.JOB_SIGNING_PUBLIC_KEY else None,
}

all_ok = True

for key, value in checks.items():
    if value:
        print(f"✅ {key}: Set")
    else:
        print(f"❌ {key}: NOT SET")
        all_ok = False

print()
print("=" * 70)

if all_ok:
    print("✅ All critical settings configured!")
    
    # Test Ed25519 key format
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        
        # Try to load private key
        private_key = serialization.load_pem_private_key(
            settings.JOB_SIGNING_PRIVATE_KEY.encode(),
            password=None
        )
        
        if isinstance(private_key, ed25519.Ed25519PrivateKey):
            print("✅ Private key is valid Ed25519 format")
        else:
            print("❌ Private key is not Ed25519 format")
            all_ok = False
            
    except Exception as e:
        print(f"❌ Error loading private key: {e}")
        all_ok = False
else:
    print("❌ Some settings are missing!")
    print()
    print("Please check backend/.env file")

print("=" * 70)

sys.exit(0 if all_ok else 1)

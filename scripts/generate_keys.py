"""
Generate Ed25519 keys for BUJA Core Platform
Run this once during initial setup
"""
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


def generate_ed25519_keys():
    """Generate Ed25519 key pair for job signing"""
    
    print("=" * 70)
    print("BUJA Core Platform - Ed25519 Key Generation")
    print("=" * 70)
    print()
    
    # Generate key pair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Serialize to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    print("✅ Keys generated successfully!")
    print()
    print("=" * 70)
    print("PRIVATE KEY (Backend .env)")
    print("=" * 70)
    print("Copy this to backend/.env as JOB_SIGNING_PRIVATE_KEY:")
    print()
    print(private_pem.decode())
    
    print("=" * 70)
    print("PUBLIC KEY (Worker agents.yaml)")
    print("=" * 70)
    print("Copy this to local_agent_hub/agents.yaml as job_signing_public_key:")
    print()
    print(public_pem.decode())
    
    print("=" * 70)
    print("⚠️  SECURITY NOTES:")
    print("=" * 70)
    print("1. NEVER commit the private key to version control")
    print("2. The public key can be distributed openly")
    print("3. Keep the private key secure - it signs all jobs")
    print("4. Rotate keys every 90 days in production")
    print("=" * 70)


if __name__ == "__main__":
    generate_ed25519_keys()

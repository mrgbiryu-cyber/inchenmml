import asyncio
import sys
import os

# Adjust path
sys.path.append(os.getcwd())

from app.core.vector_store import PineconeClient

# [UTF-8]
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def diagnose_pinecone():
    print("=== Pinecone Metadata Diagnosis ===")
    pc = PineconeClient()
    
    if not pc.index:
        print("❌ Not connected to Pinecone.")
        return

    # 1. Fetch random vector to see schema
    print("\n[1] Fetching random vector to inspect metadata schema...")
    try:
        # Query with dummy vector, broad namespace
        dummy = [0.1] * 1536
        results = pc.index.query(
            vector=dummy,
            top_k=1,
            include_metadata=True,
            namespace="knowledge"
        )
        
        if results.matches:
            match = results.matches[0]
            print(f"✅ Found vector ID: {match.id}")
            print("   Metadata Keys Found:")
            for k, v in match.metadata.items():
                print(f"   - {k}: {v} (Type: {type(v).__name__})")
                
            # Check for tenant_id vs project_id
            if 'tenant_id' in match.metadata:
                print("   ℹ️ 'tenant_id' key exists (Correct for isolation).")
            else:
                print("   ⚠️ 'tenant_id' key MISSING.")
                
            if 'project_id' in match.metadata:
                print("   ℹ️ 'project_id' key exists.")
        else:
            print("⚠️ Index 'knowledge' namespace seems empty.")
            
    except Exception as e:
        print(f"❌ Error fetching: {e}")

    # 2. Check specifically for system-master
    print("\n[2] Checking specific counts for 'system-master'...")
    try:
        # Try both keys just in case
        filter_tenant = {"tenant_id": "system-master"}
        filter_project = {"project_id": "system-master"}
        
        # We can't count easily in Pinecone without listing, but we can query
        # Let's try to fetch by ID prefix if we know any, or just query again with filter
        
        res_t = pc.index.query(vector=dummy, top_k=5, filter=filter_tenant, namespace="knowledge")
        res_p = pc.index.query(vector=dummy, top_k=5, filter=filter_project, namespace="knowledge")
        
        print(f"   Matches for tenant_id='system-master': {len(res_t.matches)}")
        print(f"   Matches for project_id='system-master': {len(res_p.matches)}")
        
        if len(res_t.matches) == 0 and len(res_p.matches) == 0:
            print("   ❌ No data found for system-master in either field.")
            print("   -> ACTION REQUIRED: Run seed ingestion.")
            
    except Exception as e:
         print(f"❌ Error checking system-master: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_pinecone())

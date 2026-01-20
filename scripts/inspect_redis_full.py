"""
Inspect ALL Redis keys to find where jobs are going
"""
import redis
import json

# Connect to Redis
r = redis.from_url("redis://localhost:6379/0", decode_responses=True)

print("=" * 70)
print("Redis Full Inspection")
print("=" * 70)
print()

# 1. Scan for Job Queues
print("1. Searching for Job Queues (job_queue:*)...")
queues = r.keys("job_queue:*")
if queues:
    for q in queues:
        length = r.llen(q)
        print(f"   found: {q} (Length: {length})")
        if length > 0:
            items = r.lrange(q, 0, -1)
            print(f"   -> First item: {items[0][:100]}...")
else:
    print("   ❌ No job queues found!")

print()

# 2. Scan for Job Specs
print("2. Searching for Job Specs (job:*:spec)...")
specs = r.keys("job:*:spec")
if specs:
    print(f"   Found {len(specs)} job specs.")
    # Show detail of the most recent one
    latest_spec_key = specs[0] # Just pick one
    spec_json = r.get(latest_spec_key)
    try:
        spec = json.loads(spec_json)
        print(f"   Sample Job ID: {spec.get('job_id')}")
        print(f"   Tenant ID: {spec.get('tenant_id')}")
        print(f"   User ID: {spec.get('user_id')}")
        print(f"   Status: {spec.get('status')}")
    except:
        print(f"   Could not parse JSON for {latest_spec_key}")
else:
    print("   ❌ No job specs found!")

print()

# 3. Check Users
print("3. Searching for Users...")
# Assuming users might be stored in Redis or we can infer from job
# Just listing keys that look like user info if any
user_keys = r.keys("user:*")
if user_keys:
    print(f"   Found {len(user_keys)} user keys.")
else:
    print("   No user keys found (Users might be in Postgres only).")

print()
print("=" * 70)

"""
Clear Redis queue and start fresh
"""
import redis

# Connect to Redis
r = redis.from_url("redis://localhost:6379/0", decode_responses=True)

print("=" * 70)
print("Clearing Redis Queue")
print("=" * 70)
print()

# Clear the job queue
queue_key = "job_queue:tenant_hyungnim"
deleted = r.delete(queue_key)

print(f"✅ Deleted queue: {queue_key}")
print(f"   Items removed: {deleted}")
print()

# Clear all job specs and results
keys = r.keys("job:*")
if keys:
    deleted_count = r.delete(*keys)
    print(f"✅ Deleted {deleted_count} job-related keys")
else:
    print("✅ No job-related keys to delete")

print()
print("=" * 70)
print("Redis is now clean. Ready for fresh jobs!")
print("=" * 70)

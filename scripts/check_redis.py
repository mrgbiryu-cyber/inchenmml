"""
Check Redis queue status
"""
import redis
import json

# Connect to Redis
r = redis.from_url("redis://localhost:6379/0", decode_responses=True)

print("=" * 70)
print("Redis Queue Status")
print("=" * 70)
print()

# Check queue length
queue_key = "job_queue:tenant_hyungnim"
queue_length = r.llen(queue_key)

print(f"Queue: {queue_key}")
print(f"Length: {queue_length}")
print()

if queue_length > 0:
    print(f"📋 {queue_length} job(s) in queue:")
    print()
    
    # Show all jobs in queue
    jobs = r.lrange(queue_key, 0, -1)
    for i, job_json in enumerate(jobs, 1):
        job = json.loads(job_json)
        print(f"{i}. Job ID: {job.get('job_id')}")
        print(f"   Status: {job.get('status')}")
        print(f"   Model: {job.get('model')}")
        print()
else:
    print("✅ Queue is empty")
    print()
    print("This means:")
    print("- Either no jobs have been created")
    print("- Or worker has already processed all jobs")

print("=" * 70)

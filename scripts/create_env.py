import os

env_content = """NEXT_PUBLIC_LANGFUSE_PROJECT_ID=your_project_id_here
NEXT_PUBLIC_API_URL=http://localhost:8002/api/v1
"""

file_path = os.path.join("frontend", ".env.local")
with open(file_path, "w", encoding="utf-8") as f:
    f.write(env_content)

print(f"Created {file_path} with UTF-8 encoding.")

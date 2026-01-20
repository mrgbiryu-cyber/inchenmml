import os

# Read existing content
env_path = os.path.join("backend", ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
else:
    content = ""

# Append keys if not present
keys_to_add = {
    "LANGFUSE_PUBLIC_KEY": "cmki0mtgh001uad07k4qkwkxr",
    "LANGFUSE_HOST": "https://cloud.langfuse.com"
}

new_content = content
for key, value in keys_to_add.items():
    if key not in new_content:
        new_content += f"\n{key}={value}"

with open(env_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Updated {env_path} with LangFuse keys.")

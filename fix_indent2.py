#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix indentation error in knowledge_service.py"""

file_path = r"d:\project\myllm\backend\app\services\knowledge_service.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix lines 520-526 (0-indexed: 519-525)
# The if/else block should be indented inside the for loop
fixes = {
    520: "                if content_key:\n",
    521: "                    hash_input = f\"{project_id}:{n_type}:{content_key}\".encode('utf-8')\n",
    522: "                    content_hash = hashlib.sha256(hash_input).hexdigest()[:16]\n",
    523: "                    n_id = f\"kg-{content_hash}\"\n",
    524: "                else:\n",
    525: "                    n_id = node.get(\"id\") or str(uuid.uuid4())\n",
}

for line_num, fixed_line in fixes.items():
    lines[line_num] = fixed_line

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Fixed indentation in knowledge_service.py")

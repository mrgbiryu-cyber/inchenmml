#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix CORS configuration to allow frontend connections"""

file_path = r"d:\project\myllm\backend\app\core\config.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the CORS_ORIGINS line
old_line = '    CORS_ORIGINS: str = "http://localhost:3000"'
new_line = '    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://100.77.67.1:3000"'

content = content.replace(old_line, new_line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Updated CORS_ORIGINS to allow localhost, 127.0.0.1, and Tailscale IP")

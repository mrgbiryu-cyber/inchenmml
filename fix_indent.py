#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix indentation error in master_agent_service.py"""

file_path = r"d:\project\myllm\backend\app\services\master_agent_service.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix lines 439-453 (0-indexed: 438-452)
# These lines should all be indented with 8 spaces (2 levels)
fixes = {
    438: "        # Phase 3: Config에 정의된 모델 전략 사용\n",
    439: "        model = settings.FALLBACK_MODEL if use_fallback else settings.PRIMARY_MODEL\n",
    440: "        \n",
    441: "        if self.config.provider == \"OLLAMA\":\n",
    442: "            if ChatOllama is None: raise ImportError(\"ChatOllama 로드 불가\")\n",
    443: "            return ChatOllama(model=model, base_url=\"http://localhost:11434\", temperature=self.config.temperature, timeout=30.0)\n",
    444: "        \n",
    445: "        # OpenRouter 기준 모델 호출\n",
    446: "        return ChatOpenAI(\n",
    447: "            model=model, \n",
    448: "            api_key=settings.OPENROUTER_API_KEY, \n",
    449: "            base_url=settings.OPENROUTER_BASE_URL, \n",
    450: "            temperature=self.config.temperature, \n",
    451: "            timeout=settings.WEB_SEARCH_TIMEOUT_SECONDS # 👈 형님이 설정하신 12초 적용\n",
    452: "        )\n",
}

for line_num, fixed_line in fixes.items():
    lines[line_num] = fixed_line

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Fixed indentation in master_agent_service.py")

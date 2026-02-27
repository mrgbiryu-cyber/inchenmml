from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class PolicyKBService:
    def __init__(self, kb_path: str = "backend/data/policy_kb/cert_ip_baseline_v1.json"):
        self.kb_path = Path(kb_path)
        self._cache: Dict[str, Any] | None = None

    def load(self) -> Dict[str, Any]:
        if self._cache is None:
            self._cache = json.loads(self.kb_path.read_text(encoding="utf-8-sig"))
        return self._cache

    def items(self) -> List[Dict[str, Any]]:
        return self.load().get("items", [])


policy_kb_service = PolicyKBService()

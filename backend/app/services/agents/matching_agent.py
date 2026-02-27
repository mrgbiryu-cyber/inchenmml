from __future__ import annotations

from typing import Any, Dict, List

from app.models.company import CompanyProfile
from app.services.knowledge.policy_kb_service import policy_kb_service


class MatchingAgent:
    """Scores certification/IP suitability based on KB keywords and profile context."""

    def _score_item(self, profile: CompanyProfile, business_plan_text: str, item: Dict[str, Any]) -> Dict[str, Any]:
        source_text = " ".join([
            profile.item_description or "",
            business_plan_text or "",
            " ".join(profile.existing_certifications or []),
            " ".join(profile.ip_assets or []),
        ]).lower()

        matched = [kw for kw in item.get("keywords", []) if kw.lower() in source_text]
        ratio = (len(matched) / len(item.get("keywords", []) or [1]))
        score = round(min(100.0, (item.get("base_weight", 0.5) * 60.0) + (ratio * 40.0)), 2)

        required = item.get("required_evidence", [])
        gaps = required[:1] if score >= 70 else required[:2]

        return {
            "category": item.get("category", "unknown"),
            "name": item.get("name", "unknown"),
            "score": score,
            "matched_keywords": matched,
            "gaps": gaps,
            "required_evidence": required,
        }

    async def calculate_suitability(self, profile: CompanyProfile, business_plan_text: str) -> Dict[str, Any]:
        items = [self._score_item(profile, business_plan_text, i) for i in policy_kb_service.items()]
        items = sorted(items, key=lambda x: x["score"], reverse=True)

        return {
            "kb_version": policy_kb_service.load().get("version", "unknown"),
            "items": items,
            "top_recommendations": items[:3],
            "overall_matching_summary": "상위 항목 중심으로 증빙 보완 후 순차 신청을 권장합니다.",
        }

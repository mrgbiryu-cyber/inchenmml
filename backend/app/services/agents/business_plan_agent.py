from __future__ import annotations

from typing import Any, Dict, List

from app.models.company import CompanyProfile


class BusinessPlanAgent:
    """Generates structured business plan output for new or existing businesses."""

    def _build_sections_for_new(self, profile: CompanyProfile) -> List[Dict[str, str]]:
        return [
            {
                "title": "문제 정의",
                "content": f"{profile.item_description}를 통해 해결하려는 시장 문제를 정리하고 고객 세그먼트를 명확히 정의합니다.",
            },
            {
                "title": "솔루션 및 BM",
                "content": "핵심 제공가치, 수익모델, 초기 유료전환 가설을 수립합니다.",
            },
            {
                "title": "실행 전략",
                "content": "초기 파일럿 고객 확보, MVP 개발, 정책지원사업 연계를 중심으로 실행 계획을 작성합니다.",
            },
        ]

    def _build_sections_for_existing(self, profile: CompanyProfile, input_text: str) -> List[Dict[str, str]]:
        excerpt = (input_text or "")[:500]
        return [
            {
                "title": "현황 분석",
                "content": f"기존 사업계획 텍스트를 기반으로 현재 사업현황을 요약합니다: {excerpt}",
            },
            {
                "title": "보완 포인트",
                "content": "정책 기준/인증 요건 대비 누락 항목(증빙, 성과지표, 실행일정)을 보완합니다.",
            },
            {
                "title": "재구성 계획",
                "content": "시장-기술-조직-재무 항목을 재정렬해 심사 친화적인 문서 구조로 재구성합니다.",
            },
        ]

    async def generate_or_reconstruct(self, profile: CompanyProfile, input_text: str = "") -> Dict[str, Any]:
        is_new = profile.classified_type and profile.classified_type.value == "PRE_ENTREPRENEUR"
        sections = self._build_sections_for_new(profile) if is_new else self._build_sections_for_existing(profile, input_text)

        return {
            "mode": "generate" if is_new else "reconstruct",
            "title": "사업계획서 초안" if is_new else "사업계획서 재구성안",
            "company_type": profile.classified_type.value if profile.classified_type else "UNKNOWN",
            "growth_stage": profile.classified_stage.value if profile.classified_stage else "UNKNOWN",
            "sections": sections,
            "analysis": {
                "needs": ["기술 명확화", "성과지표 정의", "로드맵 정합성"],
                "risk_flags": ["근거 데이터 부족"],
            },
        }

from __future__ import annotations

from typing import Any, Dict, List

from app.models.company import CompanyProfile


class RoadmapAgent:
    """Builds a three-year growth roadmap from matching outputs."""

    async def generate_roadmap(self, profile: CompanyProfile, matched_data: Dict[str, Any]) -> Dict[str, Any]:
        top = matched_data.get("top_recommendations", [])
        top_names = [i.get("name", "") for i in top]

        yearly_plan: List[Dict[str, Any]] = [
            {
                "year": "Y1",
                "goals": ["사업계획 정합성 강화", "초기 인증 준비"],
                "actions": [
                    "핵심 문제/고객정의 재검증",
                    "상위 추천 인증/지재권 증빙자료 수집",
                    "분기 KPI 설정",
                ],
                "dependencies": ["사업계획서 초안 확정"],
                "deliverables": ["사업계획서 v1", "인증/IP 준비 체크리스트"],
            },
            {
                "year": "Y2",
                "goals": ["인증/IP 실행", "R&D 연계"],
                "actions": [
                    "우선순위 1~2개 인증 신청",
                    "특허/상표 출원 실행",
                    "지원사업/R&D 과제 제안서 제출",
                ],
                "dependencies": ["Y1 증빙 완성", "내부 담당자 지정"],
                "deliverables": ["인증 신청 패키지", "IP 출원 문서"],
            },
            {
                "year": "Y3",
                "goals": ["스케일업/투자 준비"],
                "actions": [
                    "성과지표 기반 IR 자료화",
                    "시장확장/파트너십 실행",
                    "운영 프로세스 표준화",
                ],
                "dependencies": ["Y2 성과데이터"],
                "deliverables": ["IR Deck", "스케일업 운영계획"],
            },
        ]

        return {
            "title": "3개년 성장 로드맵",
            "company_type": profile.classified_type.value if profile.classified_type else "UNKNOWN",
            "growth_stage": profile.classified_stage.value if profile.classified_stage else "UNKNOWN",
            "priority_targets": top_names,
            "yearly_plan": yearly_plan,
        }

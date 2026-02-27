from __future__ import annotations

import json
from typing import Any, Dict

from fastapi.encoders import jsonable_encoder

from app.core.database import get_latest_growth_artifact, get_latest_growth_run, save_growth_run
from app.models.company import CompanyProfile
from app.services.agents.business_plan_agent import BusinessPlanAgent
from app.services.agents.classification_agent import ClassificationAgent
from app.services.agents.matching_agent import MatchingAgent
from app.services.agents.roadmap_agent import RoadmapAgent
from app.services.templates.artifact_renderer import (
    render_business_plan_html,
    render_matching_html,
    render_roadmap_html,
)
from app.services.templates.pdf_renderer import render_pdf_from_html


class GrowthSupportService:
    """E2E growth support pipeline with in-memory cache and DB persistence."""

    def __init__(self):
        self.classifier = ClassificationAgent()
        self.plan_agent = BusinessPlanAgent()
        self.matching_agent = MatchingAgent()
        self.roadmap_agent = RoadmapAgent()
        self.artifact_cache: Dict[str, Dict[str, Any]] = {}

    async def run_pipeline(self, project_id: str, profile: CompanyProfile, input_text: str = "") -> Dict[str, Any]:
        classification = await self.classifier.analyze(profile)
        business_plan = await self.plan_agent.generate_or_reconstruct(profile, input_text=input_text)
        plan_text = "\n".join([s.get("content", "") for s in business_plan.get("sections", [])])
        matching = await self.matching_agent.calculate_suitability(profile, plan_text)
        roadmap = await self.roadmap_agent.generate_roadmap(profile, matching)

        artifacts = {
            "business_plan": {
                "json": business_plan,
                "html": render_business_plan_html(business_plan),
                "markdown": self._to_markdown(business_plan),
            },
            "matching": {
                "json": matching,
                "html": render_matching_html(matching),
                "markdown": self._to_markdown(matching),
            },
            "roadmap": {
                "json": roadmap,
                "html": render_roadmap_html(roadmap),
                "markdown": self._to_markdown(roadmap),
            },
        }

        payload = {
            "project_id": project_id,
            "classification": classification,
            "business_plan": business_plan,
            "matching": matching,
            "roadmap": roadmap,
            "artifacts": artifacts,
        }
        payload = json.loads(json.dumps(jsonable_encoder(payload), ensure_ascii=False))

        self.artifact_cache[project_id] = payload
        await save_growth_run(project_id, result_json=payload, artifacts=artifacts)
        return payload

    async def get_latest(self, project_id: str) -> Dict[str, Any] | None:
        cached = self.artifact_cache.get(project_id)
        if cached:
            return cached
        return await get_latest_growth_run(project_id)

    async def get_artifact(self, project_id: str, artifact_type: str, format_name: str = "html") -> Any:
        data = await self.get_latest(project_id)
        if not data:
            raise KeyError("No pipeline result found")

        artifacts = data.get("artifacts", {})
        item = artifacts.get(artifact_type)
        if not item:
            raise KeyError(f"Artifact not found: {artifact_type}")

        if format_name == "pdf":
            html = item.get("html")
            if not html:
                html = await get_latest_growth_artifact(project_id, artifact_type, "html")
            if not html:
                raise KeyError("HTML source for PDF not found")
            return render_pdf_from_html(html)

        if format_name not in item:
            stored = await get_latest_growth_artifact(project_id, artifact_type, format_name)
            if not stored:
                raise KeyError(f"Format not found: {format_name}")
            return stored

        return item[format_name]

    def _to_markdown(self, data: Dict[str, Any]) -> str:
        lines = ["# Generated Artifact", ""]
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"## {k}")
                for row in v:
                    lines.append(f"- {row}")
            else:
                lines.append(f"- **{k}**: {v}")
        return "\n".join(lines)


growth_support_service = GrowthSupportService()

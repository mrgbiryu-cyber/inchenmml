from typing import Dict, Any

from app.models.company import CompanyProfile, CompanyType, GrowthStage
from app.services.rules import RulesEngine, ruleset_repository


class ClassificationAgent:
    """RuleSet-driven company type and growth stage classifier."""

    async def analyze(self, profile: CompanyProfile) -> Dict[str, Any]:
        ruleset = ruleset_repository.get_active("company-growth-default")
        engine = RulesEngine(ruleset)
        result = engine.classify_profile(profile)

        type_eval = result["company_type"]
        stage_eval = result["growth_stage"]

        profile.classified_type = CompanyType(type_eval.value)
        profile.classified_stage = GrowthStage(stage_eval.value)
        profile.ruleset_id = type_eval.ruleset_id
        profile.ruleset_version = type_eval.ruleset_version
        profile.confidence = min(type_eval.confidence, stage_eval.confidence)
        profile.reason_codes = list(dict.fromkeys(type_eval.reason_codes + stage_eval.reason_codes))
        profile.diagnostic_comments = (
            f"Ruleset {profile.ruleset_version} classified as "
            f"{profile.classified_type.value}/{profile.classified_stage.value}."
        )

        return {
            "trace_id": result["trace_id"],
            "classified_type": profile.classified_type,
            "classified_stage": profile.classified_stage,
            "confidence": profile.confidence,
            "reason_codes": profile.reason_codes,
            "ruleset_id": profile.ruleset_id,
            "ruleset_version": profile.ruleset_version,
            "comments": profile.diagnostic_comments,
            "company_type_eval": type_eval,
            "growth_stage_eval": stage_eval,
        }

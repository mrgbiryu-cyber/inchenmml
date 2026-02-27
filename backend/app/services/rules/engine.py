import uuid
from typing import Any, Dict, List, Optional

from app.models.company import CompanyProfile, CompanyType, GrowthStage
from app.models.schemas import RuleDefinition, RuleEvalResult, RuleSet, RuleTrace


class RulesEngine:
    """Deterministic rules engine for company type and growth stage."""

    def __init__(self, ruleset: RuleSet):
        self.ruleset = ruleset

    def _get_field(self, profile: CompanyProfile, field: str) -> Any:
        return getattr(profile, field, None)

    def _match_condition(self, actual: Any, op: str, expected: Any) -> bool:
        if op == "exists":
            return actual is not None
        if op == "eq":
            return actual == expected
        if op == "neq":
            return actual != expected
        if op == "gt":
            return actual is not None and actual > expected
        if op == "gte":
            return actual is not None and actual >= expected
        if op == "lt":
            return actual is not None and actual < expected
        if op == "lte":
            return actual is not None and actual <= expected
        if op == "in":
            return actual in expected if expected is not None else False
        return False

    def _is_rule_matched(self, profile: CompanyProfile, rule: RuleDefinition) -> bool:
        if not rule.enabled:
            return False
        for cond in rule.conditions:
            actual = self._get_field(profile, cond.field)
            if not self._match_condition(actual, cond.op, cond.value):
                return False
        return True

    def _evaluate(self, profile: CompanyProfile, rules: List[RuleDefinition], target: str, default_value: str) -> RuleEvalResult:
        totals: Dict[str, float] = {}
        reason_codes: List[str] = []
        matched_rules: List[RuleTrace] = []
        unmatched_rules: List[RuleTrace] = []
        target_weight = float(self.ruleset.weights.get(target, 1.0))

        for rule in rules:
            matched = self._is_rule_matched(profile, rule)
            if not matched:
                unmatched_rules.append(RuleTrace(rule_id=rule.rule_id, matched=False, score_delta=0.0, reason_code=None))
                continue

            local_score = 0.0
            matched_reason_codes: List[str] = []
            for action in rule.actions:
                if action.target != target:
                    continue
                delta = action.score * rule.weight * target_weight
                local_score += delta
                totals[str(action.value)] = totals.get(str(action.value), 0.0) + delta
                if action.reason_code:
                    reason_codes.append(action.reason_code)
                    matched_reason_codes.append(action.reason_code)
            rule_reason_code = matched_reason_codes[-1] if matched_reason_codes else None
            matched_rules.append(
                RuleTrace(
                    rule_id=rule.rule_id,
                    matched=True,
                    score_delta=local_score,
                    reason_code=rule_reason_code,
                )
            )

        if totals:
            sorted_items = sorted(totals.items(), key=lambda x: x[1], reverse=True)
            value, score = sorted_items[0]
            total_score = sum(v for _, v in sorted_items)
            confidence = score / total_score if total_score > 0 else 0.0
            minimum_confidence = self._read_minimum_confidence(target)
            if minimum_confidence is not None and confidence < minimum_confidence:
                fallback_triggered = self.ruleset.fallback_policy.get("fallback_on_low_confidence", True)
                if fallback_triggered:
                    value = default_value
                    score = 0.0
                    confidence = float(self.ruleset.fallback_policy.get("default_confidence", 0.4))
                    reason_codes.append(f"fallback:{target}:low_confidence")
        else:
            value = default_value
            score = 0.0
            confidence = float(self.ruleset.fallback_policy.get("default_confidence", 0.4))
            reason_codes.append(f"fallback:{target}")

        return RuleEvalResult(
            target=target,
            value=value,
            score=round(score, 4),
            confidence=round(confidence, 4),
            reason_codes=reason_codes,
            ruleset_id=self.ruleset.ruleset_id,
            ruleset_version=self.ruleset.version,
            matched_rules=matched_rules,
            unmatched_rules=unmatched_rules,
        )

    def _read_minimum_confidence(self, target: str) -> Optional[float]:
        raw_cutoff = self.ruleset.cutoffs.get("minimum_confidence")
        if raw_cutoff is None:
            return None

        try:
            return float(raw_cutoff)
        except (TypeError, ValueError):
            pass

        if isinstance(raw_cutoff, dict):
            candidate = raw_cutoff.get(target)
            if candidate is not None:
                try:
                    return float(candidate)
                except (TypeError, ValueError):
                    return None
            candidate = raw_cutoff.get("default")
            if candidate is not None:
                try:
                    return float(candidate)
                except (TypeError, ValueError):
                    return None
        return None

    def classify_company_type(self, profile: CompanyProfile) -> RuleEvalResult:
        return self._evaluate(
            profile,
            self.ruleset.company_type_rules,
            target="company_type",
            default_value=CompanyType.EARLY_STAGE.value,
        )

    def classify_growth_stage(self, profile: CompanyProfile) -> RuleEvalResult:
        return self._evaluate(
            profile,
            self.ruleset.growth_stage_rules,
            target="growth_stage",
            default_value=GrowthStage.STARTUP.value,
        )

    def classify_profile(self, profile: CompanyProfile) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        type_eval = self.classify_company_type(profile)
        stage_eval = self.classify_growth_stage(profile)
        return {
            "trace_id": trace_id,
            "company_type": type_eval,
            "growth_stage": stage_eval,
        }

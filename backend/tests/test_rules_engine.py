from app.models.company import CompanyProfile
from app.models.schemas import RuleDefinition, RuleSet
from app.services.rules.engine import RulesEngine


def build_ruleset() -> RuleSet:
    return RuleSet(
        ruleset_id="company-growth-default",
        version="vtest",
        status="active",
        company_type_rules=[
            {
                "rule_id": "ct-pre",
                "name": "pre",
                "conditions": [
                    {"field": "has_corporation", "op": "eq", "value": False},
                    {"field": "annual_revenue", "op": "lte", "value": 0},
                ],
                "actions": [
                    {
                        "target": "company_type",
                        "value": "PRE_ENTREPRENEUR",
                        "score": 1.0,
                        "reason_code": "CT_PRE",
                    }
                ],
            }
        ],
        growth_stage_rules=[
            {
                "rule_id": "gs-seed",
                "name": "seed",
                "conditions": [
                    {"field": "years_in_business", "op": "lte", "value": 1},
                    {"field": "employee_count", "op": "lte", "value": 3},
                ],
                "actions": [
                    {
                        "target": "growth_stage",
                        "value": "SEED",
                        "score": 1.0,
                        "reason_code": "GS_SEED",
                    }
                ],
            }
        ],
        fallback_policy={"default_confidence": 0.4},
    )


def test_rules_engine_classifies_seed_pre_entrepreneur():
    engine = RulesEngine(build_ruleset())
    profile = CompanyProfile(
        item_description="new idea",
        has_corporation=False,
        annual_revenue=0,
        years_in_business=0,
        employee_count=1,
    )

    result = engine.classify_profile(profile)

    assert result["company_type"].value == "PRE_ENTREPRENEUR"
    assert result["growth_stage"].value == "SEED"
    assert "CT_PRE" in result["company_type"].reason_codes
    assert "GS_SEED" in result["growth_stage"].reason_codes


def test_rules_engine_fallback_when_no_match():
    ruleset = build_ruleset()
    ruleset.company_type_rules = []
    ruleset.growth_stage_rules = []
    engine = RulesEngine(ruleset)

    profile = CompanyProfile(item_description="x", years_in_business=5, annual_revenue=100, employee_count=10)
    result = engine.classify_profile(profile)

    assert result["company_type"].value == "EARLY_STAGE"
    assert result["growth_stage"].value == "STARTUP"
    assert result["company_type"].confidence == 0.4
    assert result["growth_stage"].confidence == 0.4


def test_rules_engine_cutoff_fallback_policy():
    ruleset = build_ruleset()
    ruleset.cutoffs = {"minimum_confidence": 0.5}
    ruleset.fallback_policy = {
        "default_confidence": 0.2,
        "fallback_on_low_confidence": True,
    }
    ruleset.company_type_rules = [
        RuleDefinition(
            rule_id="ct_low_1",
            name="low confidence option A",
            conditions=[],
            actions=[
                {
                    "target": "company_type",
                    "value": "GROWTH_STAGE",
                    "score": 1.0,
                    "reason_code": "CT_LOW_A",
                }
            ],
        ),
        RuleDefinition(
            rule_id="ct_low_2",
            name="low confidence option B",
            conditions=[],
            actions=[
                {
                    "target": "company_type",
                    "value": "PRE_ENTREPRENEUR",
                    "score": 0.2,
                    "reason_code": "CT_LOW_B",
                }
            ],
        ),
        RuleDefinition(
            rule_id="ct_low_3",
            name="low confidence option C",
            conditions=[],
            actions=[
                {
                    "target": "company_type",
                    "value": "STARTUP",
                    "score": 0.2,
                    "reason_code": "CT_LOW_C",
                }
            ],
        ),
    ]
    # Keep growth stage classification deterministic for baseline path.
    ruleset.growth_stage_rules = [build_ruleset().growth_stage_rules[0]]
    engine = RulesEngine(ruleset)

    profile = CompanyProfile(
        item_description="x",
        has_corporation=False,
        annual_revenue=0,
        years_in_business=0,
        employee_count=1,
    )

    result = engine.classify_profile(profile)

    # ct_low_1 score 1.0, ct_low_2/3 each 0.2 => confidence=0.7143, so no fallback
    assert result["company_type"].value == "GROWTH_STAGE"
    assert result["company_type"].confidence == 0.7143
    assert "CT_LOW_A" in result["company_type"].reason_codes

    # force low-confidence winner ratio by lowering winning score
    ruleset.company_type_rules[0].actions[0].score = 0.1
    ruleset.company_type_rules[1].actions[0].score = 0.3
    ruleset.company_type_rules[2].actions[0].score = 0.3
    result = engine.classify_profile(profile)
    assert result["company_type"].value == "EARLY_STAGE"
    assert result["company_type"].confidence == 0.2
    assert "fallback:company_type:low_confidence" in result["company_type"].reason_codes

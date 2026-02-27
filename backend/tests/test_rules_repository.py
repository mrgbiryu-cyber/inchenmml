import uuid

from app.models.schemas import RuleSet, RuleStatus
from app.services.rules.repository import RulesetRepository


def test_ruleset_repository_create_activate_clone():
    repo = RulesetRepository(f"backend/data/rulesets_test_{uuid.uuid4().hex}")

    base = RuleSet(
        ruleset_id="company-growth-default",
        version="v1",
        status=RuleStatus.ACTIVE,
        company_type_rules=[],
        growth_stage_rules=[],
    )
    repo.create(base)

    clone = repo.clone("company-growth-default", "v1", "v1.1", author="tester")
    assert clone.version == "v1.1"
    assert clone.status == RuleStatus.DRAFT

    activated = repo.activate("company-growth-default", "v1.1")
    assert activated.status == RuleStatus.ACTIVE

    active = repo.get_active("company-growth-default")
    assert active.version == "v1.1"

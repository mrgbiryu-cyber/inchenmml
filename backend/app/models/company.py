from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class CompanyType(str, Enum):
    PRE_ENTREPRENEUR = "PRE_ENTREPRENEUR"
    EARLY_STAGE = "EARLY_STAGE"
    GROWTH_STAGE = "GROWTH_STAGE"
    TRANSITION = "TRANSITION"


class GrowthStage(str, Enum):
    SEED = "SEED"
    STARTUP = "STARTUP"
    SCALEUP = "SCALEUP"
    ADVANCED = "ADVANCED"
    TRANSITION = "TRANSITION"


class CompanyProfile(BaseModel):
    """Normalized company profile used by rules and planning agents."""

    company_name: Optional[str] = None
    company_id: Optional[str] = None
    industry_code: Optional[str] = None
    founding_date: Optional[str] = None
    years_in_business: int = 0
    annual_revenue: float = 0.0
    last_fiscal_year_revenue: Optional[float] = None
    employee_count: int = 0
    employee_growth_rate: Optional[float] = None
    item_description: str = Field(..., description="BM or idea description")
    has_corporation: bool = False
    existing_certifications: List[str] = Field(default_factory=list)
    has_rnd_org: Optional[bool] = None
    ip_assets: List[str] = Field(default_factory=list)
    document_sources: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Determined by classification
    classified_type: Optional[CompanyType] = None
    classified_stage: Optional[GrowthStage] = None
    diagnostic_comments: Optional[str] = Field(None, description="Classification rationale")
    ruleset_id: Optional[str] = None
    ruleset_version: Optional[str] = None
    confidence: Optional[float] = None
    reason_codes: List[str] = Field(default_factory=list)


class RoadmapTimeline(BaseModel):
    year: str
    strategy_goal: str
    action_items: List[str]
    target_certifications: List[str]
    target_ip: List[str]


class GrowthRoadmap(BaseModel):
    overall_strategy: str
    timelines: List[RoadmapTimeline]

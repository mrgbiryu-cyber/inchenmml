"""
Pydantic models for BUJA Core Platform
Defines schemas for Jobs, Users, and API requests/responses
"""
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, validator
from .company import CompanyProfile


# ============================================
# Enums (from specifications)
# ============================================

class UserRole(str, Enum):
    """User role hierarchy"""
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    STANDARD_USER = "standard_user"


class ProviderType(str, Enum):
    """LLM Provider type"""
    OPENROUTER = "OPENROUTER"  # Cloud API
    OLLAMA = "OLLAMA"  # Local LLM


class ExecutionLocation(str, Enum):
    """Where the job execution happens"""
    CLOUD = "CLOUD"  # Backend executes immediately
    LOCAL_MACHINE = "LOCAL_MACHINE"  # Job sent to Worker


class JobStatus(str, Enum):
    """Job lifecycle states"""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FailureReason(str, Enum):
    """Job failure substates"""
    TIMEOUT = "TIMEOUT"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    WORKER_DISCONNECTED = "WORKER_DISCONNECTED"
    INVALID_JOB = "INVALID_JOB"


class Intent(str, Enum):
    """Intent categories for dispatcher"""
    CODING = "CODING"
    PLANNING = "PLANNING"
    CHAT = "CHAT"
    CODE_REVIEW = "CODE_REVIEW"


# ============================================
# Job Models (COMPLETE SPECIFICATION)
# ============================================

class FileOperation(BaseModel):
    """File operation within a job"""
    action: str = Field(..., description="CREATE | MODIFY | DELETE")
    path: str = Field(..., description="Relative path to file")
    content: Optional[str] = Field(None, description="File content (for CREATE/MODIFY)")
    description: Optional[str] = Field(None, description="Human-readable description")


class JobMetadata(BaseModel):
    """Optional metadata for jobs"""
    objective: Optional[str] = None
    requirements: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    language: str = "Python"
    framework: str = "FastAPI"
    code_style: str = "Black + isort"
    notes: Optional[str] = None
    input: Optional[str] = None
    estimated_files: Optional[int] = None
    request_source: Optional[str] = None
    user_context: Optional[str] = None
    
    class Config:
        extra = "allow" # Allow arbitrary fields like role, system_prompt


class JobCreate(BaseModel):
    """Request to create a new job"""
    execution_location: ExecutionLocation
    provider: ProviderType
    model: str
    timeout_sec: int = Field(default=600, ge=1, le=3600)
    
    # Conditional: Required if execution_location == LOCAL_MACHINE
    repo_root: Optional[str] = None
    allowed_paths: Optional[List[str]] = None
    tool_allowlist: List[str] = Field(default_factory=list)
    
    # Optional
    steps: List[str] = Field(default_factory=list)
    priority: int = Field(default=5, ge=1, le=10)
    metadata: JobMetadata = Field(default_factory=JobMetadata)
    file_operations: List[FileOperation] = Field(default_factory=list)
    
    @validator('repo_root', 'allowed_paths')
    def validate_local_machine_fields(cls, v, values):
        """Ensure repo_root and allowed_paths are provided for LOCAL_MACHINE jobs"""
        if values.get('execution_location') == ExecutionLocation.LOCAL_MACHINE:
            if v is None:
                raise ValueError(
                    "repo_root and allowed_paths are required for LOCAL_MACHINE execution"
                )
        return v


class Job(BaseModel):
    """
    Complete Job specification
    Follows JOB_AND_SECURITY.md Section 3.2
    """
    # REQUIRED fields
    job_id: UUID = Field(..., description="Unique identifier")
    tenant_id: str = Field(..., min_length=3, max_length=50)
    user_id: str = Field(..., min_length=3, max_length=50)
    execution_location: ExecutionLocation
    provider: ProviderType
    model: str
    created_at_ts: int = Field(..., description="Unix timestamp (seconds)")
    status: JobStatus
    timeout_sec: int = Field(..., ge=1, le=3600)
    idempotency_key: str = Field(..., description="sha256:...")
    signature: str = Field(..., description="base64:... (Ed25519)")
    
    # CONDITIONAL: Required if execution_location == LOCAL_MACHINE
    repo_root: Optional[str] = None
    allowed_paths: Optional[List[str]] = None
    tool_allowlist: List[str] = Field(default_factory=list)
    
    # OPTIONAL
    steps: List[str] = Field(default_factory=list)
    priority: int = Field(default=5, ge=1, le=10)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    file_operations: List[FileOperation] = Field(default_factory=list)
    
    # Runtime fields (not in initial creation)
    retry_count: int = Field(default=0)
    reassign_count: int = Field(default=0)
    execution_started_at: Optional[int] = None
    
    # [NEW] Version 3.5.1 Result Fields
    large_change_detected: bool = False
    git_diff_stat: Optional[str] = None
    total_changed_lines: int = 0
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_id": "tenant_hyungnim",
                "user_id": "user_001",
                "execution_location": "LOCAL_MACHINE",
                "provider": "OLLAMA",
                "model": "mimo-v2-flash",
                "created_at_ts": 1704067200,
                "status": "QUEUED",
                "timeout_sec": 600,
                "idempotency_key": "sha256:a3f5c8d2e1b4...",
                "signature": "base64:SGVsbG9Xb3JsZA==...",
                "repo_root": "/home/user/projects/buja",
                "allowed_paths": ["src/", "tests/", "docs/"],
                "steps": ["analyze", "code", "test"],
                "priority": 7
            }
        }


class JobResult(BaseModel):
    """Job execution result"""
    status: JobStatus
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    metrics: Optional[Dict[str, Any]] = None


class JobStatusResponse(BaseModel):
    """Response for job status query"""
    job_id: UUID
    status: JobStatus
    progress: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[JobResult] = None


# ============================================
# User Models
# ============================================

class UserQuota(BaseModel):
    """Resource limits for a user"""
    max_daily_jobs: int = 100
    max_concurrent_jobs: int = 5
    max_storage_mb: int = 1024  # 1GB
    
    # Current usage (reset periodically)
    current_daily_jobs: int = 0
    current_storage_mb: int = 0


class Domain(BaseModel):
    """Represents a project/repository"""
    id: str = Field(..., description="Unique ID (e.g., 'project-alpha')")
    name: str
    repo_root: str
    description: Optional[str] = None
    owner_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    agent_config: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration (model, provider, etc.)")


class User(BaseModel):
    """User model"""
    id: str
    username: str
    email: Optional[str] = None
    tenant_id: str
    role: UserRole
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    # New fields for quota and permissions
    quota: UserQuota = Field(default_factory=UserQuota)
    allowed_domains: List[str] = Field(default_factory=list, description="List of domain IDs this user can access")
    
    class Config:
        from_attributes = True


class UserInDB(User):
    """User model with hashed password"""
    hashed_password: str


# ============================================
# Authentication Models
# ============================================

class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Seconds until expiration")


class TokenData(BaseModel):
    """Decoded JWT token data"""
    sub: str = Field(..., description="User ID")
    tenant_id: str
    role: UserRole
    exp: Optional[int] = None


class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str


# ============================================
# API Response Models
# ============================================

class JobCreateResponse(BaseModel):
    """Response when creating a job"""
    job_id: UUID
    status: JobStatus
    message: str = "Job queued successfully"


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# ============================================
# RuleSet Models
# ============================================

class RuleStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RuleCondition(BaseModel):
    field: str
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in", "exists"]
    value: Optional[Any] = None


class RuleAction(BaseModel):
    target: str = Field(..., description="company_type | growth_stage | matching_score")
    value: Any
    score: float = 0.0
    reason_code: str


class RuleDefinition(BaseModel):
    rule_id: str
    name: str
    conditions: List[RuleCondition] = Field(default_factory=list)
    actions: List[RuleAction] = Field(default_factory=list)
    weight: float = 1.0
    enabled: bool = True


class RuleSet(BaseModel):
    ruleset_id: str
    version: str
    status: RuleStatus = RuleStatus.DRAFT
    description: Optional[str] = None
    effective_from: Optional[datetime] = None
    author: Optional[str] = None
    company_type_rules: List[RuleDefinition] = Field(default_factory=list)
    growth_stage_rules: List[RuleDefinition] = Field(default_factory=list)
    matching_rules: List[RuleDefinition] = Field(default_factory=list)
    weights: Dict[str, float] = Field(default_factory=dict)
    cutoffs: Dict[str, float] = Field(default_factory=dict)
    fallback_policy: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RuleTrace(BaseModel):
    rule_id: str
    matched: bool
    score_delta: float = 0.0
    reason_code: Optional[str] = None


class RuleEvalResult(BaseModel):
    target: str
    value: str
    score: float = 0.0
    confidence: float = 0.0
    reason_codes: List[str] = Field(default_factory=list)
    ruleset_id: str
    ruleset_version: str
    matched_rules: List[RuleTrace] = Field(default_factory=list)
    unmatched_rules: List[RuleTrace] = Field(default_factory=list)


class RuleSetPreviewRequest(BaseModel):
    profile: CompanyProfile


class RuleSetCloneRequest(BaseModel):
    version: str = Field(..., description="new version label, e.g. v1.1")
    description: Optional[str] = None


# ============================================
# Project & Agent Models (Phase 1 & 2)
# ============================================

class AgentType(str, Enum):
    """Agent types for schema validation and UI only"""
    MASTER = "MASTER"
    PLANNER = "PLANNER"
    CODER = "CODER"
    QA = "QA"
    GIT = "GIT"
    CUSTOM = "CUSTOM"
    CLASSIFICATION = "CLASSIFICATION"
    BUSINESS_PLAN = "BUSINESS_PLAN"
    MATCHING = "MATCHING"
    ROADMAP = "ROADMAP"

class AgentDefinition(BaseModel):
    """Defines a single agent in a workflow"""
    agent_id: str
    name: str = "Unknown Agent"
    type: AgentType = AgentType.CUSTOM
    role: str = Field(..., description="PLANNER | CODER | REVIEWER | QA")
    model: str
    provider: ProviderType
    system_prompt: str
    toolset: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    next_agents: List[str] = Field(default_factory=list)
    enabled: bool = True

    @validator('config')
    def validate_config_by_type(cls, v, values):
        agent_type = values.get('type')
        if not agent_type or not v: # 빈 설정은 통과 (repair 모드 지원)
            return v
            
        if agent_type == AgentType.CODER:
            required = ['repo_root', 'allowed_paths', 'mode', 'change_policy', 'language_stack']
        elif agent_type == AgentType.QA:
            required = ['repo_root', 'test_command', 'retry_limit', 'timeout_sec', 'artifact_output']
        elif agent_type == AgentType.GIT:
            required = ['repo_root', 'remote_name', 'default_branch', 'push_strategy', 'allowed_commands']
        elif agent_type == AgentType.CUSTOM:
            required = ['repo_root', 'allowed_paths', 'tool_allowlist', 'risk_level']
        else:
            return v
            
        # Partial validation: missing fields are OK during database loading
        # The master agent will handle filling these via MISSION READINESS REPORT
        return v

    class Config:
        extra = "allow"


class ProjectAgentConfig(BaseModel):
    """Configuration for agents in a project"""
    workflow_type: Literal["SEQUENTIAL", "PARALLEL", "CUSTOM"]
    agents: List[AgentDefinition]
    entry_agent_id: str


class ChatMessageResponse(BaseModel):
    """Schema for chat message response (Frontend Compatible)"""
    id: str = Field(..., description="Message UUID")
    role: str = Field(..., description="user | assistant | system")
    content: str
    created_at: str = Field(..., description="ISO formatted timestamp")
    thread_id: Optional[str] = None
    project_id: Optional[str] = None
    request_id: Optional[str] = None # [v4.2] Source Tracking ID

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    """Request to create a new project"""
    name: str
    description: Optional[str] = None
    project_type: Literal["EXISTING", "NEW", "GROWTH_SUPPORT"] = "GROWTH_SUPPORT"
    repo_path: Optional[str] = None
    company_profile: Optional[CompanyProfile] = None
    agent_config: Optional[ProjectAgentConfig] = None

class Project(BaseModel):
    """Project model"""
    id: str = Field(..., description="UUID")
    name: str
    description: Optional[str] = None
    project_type: Literal["EXISTING", "NEW", "SYSTEM", "GROWTH_SUPPORT"] = "GROWTH_SUPPORT"
    repo_path: Optional[str] = None
    company_profile: Optional[CompanyProfile] = None
    tenant_id: str
    user_id: str = "system"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Agent Config
    agent_config: Optional[ProjectAgentConfig] = None

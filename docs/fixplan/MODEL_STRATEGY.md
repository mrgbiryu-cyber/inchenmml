# MODEL STRATEGY - Cost / Speed / Stability Optimization

**Issue**: H7 - 모델 전략 미정리, DeepSeek/GPT 혼용, 단계별 모델 변경으로 재현 불가  
**Evidence**: Config files, service implementations, hardcoded model references  
**Goal**: Fixed primary model, clear fallback policy, cost predictability

---

## Current State (Evidence)

### Configuration
- **File**: `backend/app/core/config.py`
  - Line 91: `LLM_HIGH_TIER_MODEL = "gpt-4o"`
  - Line 92: `LLM_LOW_TIER_MODEL = "gpt-4o-mini"`
  - Line 43: `OPENROUTER_API_KEY`

### Master Agent
- **File**: `backend/app/models/master.py`
  - Line 7: `model: str = "gpt-4o"`
  - Line 8: `provider: Literal["OPENROUTER", "OLLAMA"] = "OPENROUTER"`
  - Line 9: `temperature: float = 0.7`

### Knowledge Service
- **File**: `backend/app/services/knowledge_service.py:59-72`
```python
def _get_llm(self, tier: str = "low"):
    if tier == "high":
        return ChatOpenAI(model=settings.LLM_HIGH_TIER_MODEL, ...)
    else:
        return ChatOpenAI(model=settings.LLM_LOW_TIER_MODEL, ...)
```

### Hardcoded Models
- **File**: `backend/app/services/master_agent_service.py:255-257`
```python
AgentDefinition(..., model="gpt-4o", provider="OPENROUTER", ...)  # Architect
AgentDefinition(..., model="gpt-4o", provider="OPENROUTER", ...)  # QA
AgentDefinition(..., model="gpt-4o", provider="OPENROUTER", ...)  # Reporter
```

### Timeout Configuration
- **File**: `backend/app/services/master_agent_service.py`
  - Line 380: Ollama timeout = 30s
  - Line 381: OpenRouter timeout = 60s

---

## Problems Identified

### Problem #1: No Primary Model Defined
**User Requirement**: "Primary (고정): DeepSeek Chat V3.1 (OpenRouter)"  
**Current**: GPT-4o is default, DeepSeek not mentioned anywhere

### Problem #2: Dynamic Model Selection
**Current**: Knowledge service switches between high/low tier  
**Issue**: Unpredictable costs, harder to reproduce bugs

### Problem #3: No Failure Handling Policy
**Current**: If LLM call fails, error propagates  
**Missing**: "RAG/Tavily 실패 시 모델 변경 금지" 원칙

### Problem #4: Scattered Configuration
**Current**: Model specified in 3+ places (config.py, master.py, hardcoded agents)  
**Issue**: Inconsistency, hard to enforce policy

---

## Design Solution

### 1. Fixed Model Hierarchy

```yaml
Primary (Always Use):
  model: deepseek/deepseek-chat-v3
  provider: OPENROUTER
  use_cases: 
    - All master agent responses
    - All workflow agent tasks (Architect, Coder, QA, Reporter, Git)
    - All knowledge extraction
  temperature: 0.7
  timeout: 60s
  
Secondary (Restricted):
  model: gpt-4o-mini
  provider: OPENROUTER
  use_cases:
    - Validation only (if explicitly allowed)
    - Summary generation (if explicitly allowed)
    - Short format conversion (≤ 500 tokens output)
  max_calls_per_session: 1
  temperature: 0.3
  timeout: 30s

Forbidden:
  - gpt-4o (too expensive for default use)
  - gpt-4-turbo
  - Any model switch on RAG/Tavily failure
  - Dynamic tier selection based on content
```

### 2. Configuration Schema (Centralized)

**File**: `backend/app/core/config.py`

**Current**:
```python
LLM_HIGH_TIER_MODEL: str = "gpt-4o"
LLM_LOW_TIER_MODEL: str = "gpt-4o-mini"
```

**Proposed**:
```python
# Model Strategy (Fixed)
PRIMARY_MODEL: str = "deepseek/deepseek-chat-v3"
PRIMARY_PROVIDER: str = "OPENROUTER"
PRIMARY_TEMPERATURE: float = 0.7
PRIMARY_TIMEOUT: int = 60

SECONDARY_MODEL: str = "gpt-4o-mini"
SECONDARY_PROVIDER: str = "OPENROUTER"
SECONDARY_TEMPERATURE: float = 0.3
SECONDARY_TIMEOUT: int = 30

# Forbidden Models (for validation)
FORBIDDEN_MODELS: List[str] = ["gpt-4o", "gpt-4-turbo", "gpt-4-32k"]
```

### 3. Centralized LLM Factory

**New File**: `backend/app/core/llm_factory.py`

```python
from enum import Enum
from langchain_openai import ChatOpenAI
from app.core.config import settings

class ModelTier(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"

class LLMFactory:
    """
    Centralized LLM creation with model strategy enforcement.
    """
    
    @staticmethod
    def get_llm(tier: ModelTier = ModelTier.PRIMARY) -> ChatOpenAI:
        """
        Get LLM instance according to model strategy.
        
        Args:
            tier: PRIMARY (always use) or SECONDARY (restricted)
            
        Returns:
            Configured ChatOpenAI instance
            
        Raises:
            ValueError: If trying to use forbidden model
        """
        if tier == ModelTier.PRIMARY:
            return ChatOpenAI(
                model=settings.PRIMARY_MODEL,
                api_key=settings.OPENROUTER_API_KEY,
                base_url=settings.OPENROUTER_BASE_URL,
                temperature=settings.PRIMARY_TEMPERATURE,
                timeout=settings.PRIMARY_TIMEOUT
            )
        elif tier == ModelTier.SECONDARY:
            # Log usage for monitoring
            logger.warning(f"SECONDARY model used: {settings.SECONDARY_MODEL}")
            return ChatOpenAI(
                model=settings.SECONDARY_MODEL,
                api_key=settings.OPENROUTER_API_KEY,
                base_url=settings.OPENROUTER_BASE_URL,
                temperature=settings.SECONDARY_TEMPERATURE,
                timeout=settings.SECONDARY_TIMEOUT
            )
        else:
            raise ValueError(f"Invalid tier: {tier}")
    
    @staticmethod
    def validate_model(model_name: str):
        """Raise error if model is forbidden."""
        if model_name in settings.FORBIDDEN_MODELS:
            raise ValueError(f"Model {model_name} is forbidden by MODEL_STRATEGY")
```

### 4. Update All Services

**master_agent_service.py**:
```python
# Before
def _get_llm(self):
    if self.config.provider == "OLLAMA":
        return ChatOllama(...)
    return ChatOpenAI(model=self.config.model, ...)

# After
from app.core.llm_factory import LLMFactory, ModelTier

def _get_llm(self):
    # Provider setting ignored - always use PRIMARY
    return LLMFactory.get_llm(ModelTier.PRIMARY)
```

**knowledge_service.py**:
```python
# Before
def _get_llm(self, tier: str = "low"):
    if tier == "high":
        return ChatOpenAI(model=settings.LLM_HIGH_TIER_MODEL, ...)
    else:
        return ChatOpenAI(model=settings.LLM_LOW_TIER_MODEL, ...)

# After
def _get_llm(self):
    # Always use PRIMARY - no tier switching
    return LLMFactory.get_llm(ModelTier.PRIMARY)
```

**orchestration_service.py**:
```python
# In _create_agent_node(), line 221-222
# Before: Dynamic provider selection
# After: Force PRIMARY model, ignore agent-level override
llm = LLMFactory.get_llm(ModelTier.PRIMARY)
```

---

## Failure Handling Policy

### RAG/Tavily Failure → Model Stays Fixed

**Scenario**: Web search fails, knowledge retrieval returns 0 results  
**Wrong Response**: Switch to GPT-4o for "better reasoning"  
**Correct Response**: Use PRIMARY model with `context=[]`

**Implementation**:
```python
# In master_agent_service.py, web_search_intelligence_tool
try:
    results = search_client.search(query)
    if not results:
        logger.warning("Tavily returned 0 results")
        results = []  # Empty context, not model switch
except Exception as e:
    logger.error(f"Tavily failed: {e}")
    results = []  # Empty context, not model switch

# Continue with PRIMARY model
llm = LLMFactory.get_llm(ModelTier.PRIMARY)
response = llm.invoke(messages + [HumanMessage(content=f"Context: {results}")])
```

### Knowledge Graph Empty → Model Stays Fixed

**Scenario**: Neo4j unreachable or returns 0 nodes  
**Correct Response**: 
```python
try:
    knowledge = await neo4j_client.query_knowledge(project_id, query)
except Exception:
    knowledge = []  # Graceful degradation

# PRIMARY model continues
llm = LLMFactory.get_llm(ModelTier.PRIMARY)
```

---

## Cost Predictability

### DeepSeek Chat V3.1 Pricing (OpenRouter)
- Input: ~$0.27 / 1M tokens
- Output: ~$1.10 / 1M tokens
- **Estimated Cost**: ~10-20x cheaper than GPT-4o

### Budget Calculation
**Current** (GPT-4o):
- 100 messages/day × 1000 tokens/msg × 2 (in+out) = 200K tokens/day
- Cost: ~$2.40/day (assuming $12/1M tokens blended rate)

**Proposed** (DeepSeek V3.1):
- Same 200K tokens/day
- Cost: ~$0.27/day (90% reduction)

### Monitoring
- **File**: `backend/app/services/knowledge_service.py:_log_cost()`
- Update to log actual DeepSeek costs
- Add daily budget alert at $5/day (configurable)

---

## Migration Plan

### Phase 1: Add LLM Factory (Non-Breaking)
- [ ] Create `backend/app/core/llm_factory.py`
- [ ] Add PRIMARY_MODEL config to `config.py`
- [ ] Test factory with existing GPT-4o model

### Phase 2: Switch Master Agent
- [ ] Update `master_agent_service.py:_get_llm()` to use factory
- [ ] Test master agent with DeepSeek
- [ ] Verify streaming works

### Phase 3: Switch Knowledge Service
- [ ] Update `knowledge_service.py:_get_llm()` to use factory
- [ ] Remove tier-based selection
- [ ] Test extraction quality

### Phase 4: Switch Orchestration Agents
- [ ] Update `orchestration_service.py` to use factory
- [ ] Remove hardcoded "gpt-4o" in agent definitions
- [ ] Test multi-agent workflow

### Phase 5: Enforce Policy
- [ ] Add model validation on agent creation
- [ ] Raise error if forbidden model specified
- [ ] Add monitoring for SECONDARY model usage

---

## Implementation Checklist

- [ ] Add PRIMARY_MODEL = "deepseek/deepseek-chat-v3" to config.py
- [ ] Create LLMFactory with PRIMARY/SECONDARY tiers
- [ ] Update master_agent_service.py to use factory
- [ ] Update knowledge_service.py to use factory (remove tier switching)
- [ ] Update orchestration_service.py to use factory
- [ ] Remove hardcoded "gpt-4o" from agent definitions
- [ ] Update cost logging to track DeepSeek usage
- [ ] Add forbidden model validation
- [ ] Document policy in README or CONTRIBUTING.md

---

## Testing Requirements

### Unit Tests
1. **Factory Creation**:
   ```python
   llm = LLMFactory.get_llm(ModelTier.PRIMARY)
   assert llm.model_name == "deepseek/deepseek-chat-v3"
   assert llm.timeout == 60
   ```

2. **Forbidden Model**:
   ```python
   with pytest.raises(ValueError):
       LLMFactory.validate_model("gpt-4o")
   ```

### Integration Tests
1. **Master Agent Response**:
   - Send message to master agent
   - Verify response generated with DeepSeek
   - Check cost log for DeepSeek usage

2. **Knowledge Extraction**:
   - Save message → trigger knowledge pipeline
   - Verify extraction used PRIMARY model
   - Verify no tier switching occurred

3. **Failure Degradation**:
   - Mock Tavily failure
   - Verify PRIMARY model still used
   - Verify `context=[]` passed to LLM

---

## Breaking Changes

**Minimal**:
- Agent configurations with `model="gpt-4o"` will be overridden
- `provider` field in MasterAgentConfig no longer used

**User Impact**:
- Existing conversations continue (no data migration needed)
- Model switch is transparent (responses will be from DeepSeek)
- Cost reduction visible in cost logs

---

## References

- `backend/app/core/config.py` - Configuration settings
- `backend/app/services/master_agent_service.py` - Master agent LLM usage
- `backend/app/services/knowledge_service.py` - Knowledge extraction LLM usage
- `backend/app/services/orchestration_service.py` - Multi-agent LLM usage
- [RAG_AUDIT_AND_DEGRADED_MODE.md](./RAG_AUDIT_AND_DEGRADED_MODE.md) - Failure handling
- [COLD_START_AND_DATA_HYGIENE.md](./COLD_START_AND_DATA_HYGIENE.md) - Graceful degradation

---

## Compliance with User Requirements

✅ **Primary (고정)**: DeepSeek Chat V3.1 (OpenRouter) - 모든 기본 생성 및 추론  
✅ **Secondary (제한적)**: gpt-4o-mini - 검증, 요약만, 명시적 허용 시 1회  
✅ **Forbidden**: Planner/Router/Fallback에서 임의 모델 선택 금지  
✅ **Failure Handling**: RAG/Tavily 실패 → 모델 유지 + context=[]  
✅ **Cost/Reproducibility**: 비용 예측 가능, 재현성 확보

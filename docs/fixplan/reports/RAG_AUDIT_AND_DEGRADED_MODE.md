# RAG AUDIT AND DEGRADED MODE - Tavily Integration & Fallback

**Issue**: H6 - Tavily(Web Search) 실존/신뢰도 불명확, REQUIRED로 가정되나 미연결/미호출  
**Evidence**: search_client.py, tool definitions, error handling  
**Goal**: Graceful degradation when Tavily unavailable or returns 0 results

---

## Evidence Summary

### Tavily Client Implementation
- **File**: `backend/app/core/search_client.py:5-37`
- **Class**: `TavilyClient`
- **Methods**: `search(query, **kwargs)`, `qna(query, **kwargs)`
- **Initialization**: Line 11-16
  ```python
  if not settings.TAVILY_API_KEY:
      print("⚠️ TAVILY_API_KEY not set. Search will not function.")
      self.client = None
  else:
      self.client = TavilySDK(api_key=settings.TAVILY_API_KEY)
  ```

### Error Handling
- **File**: `backend/app/core/search_client.py:35`
  ```python
  except Exception as e:
      print(f"❌ Tavily search failed: {e}")
      return []
  ```
- **Issue**: Returns empty list, but caller doesn't know if it's 0 results or failure

### Tool Integration
- **File**: `backend/app/services/master_agent_service.py:49-61`
  ```python
  @tool
  def web_search_intelligence_tool(query: str) -> str:
      client = TavilyClient()
      results = client.search(query, max_results=5)
      if not results:
          return "검색 결과가 없습니다."
      # Format results...
  ```
- **Issue**: No distinction between "Tavily failed" vs "Tavily returned 0 results"

---

## Tavily Readiness Audit (6 Checks)

### ✅ Check 1: Tavily Client Exists
- **File**: `backend/app/core/search_client.py:5-37`
- **Status**: PASS - Client implemented

### ✅ Check 2: TAVILY_API_KEY Loaded
- **File**: `backend/app/core/config.py:47`
  ```python
  TAVILY_API_KEY: Optional[str] = None
  ```
- **Status**: PASS - Key configurable (but optional)

### ❌ Check 3: Actual Request Sent
- **File**: `backend/app/core/search_client.py:26`
  ```python
  result = self.client.search(query=query, **kwargs)
  ```
- **Status**: UNKNOWN - No logging of actual HTTP request
- **Fix Needed**: Add request logging

### ❌ Check 4: Timeout Configured
- **File**: `backend/app/core/search_client.py`
- **Status**: FAIL - No timeout parameter found
- **Risk**: Tavily call could hang indefinitely

### ❌ Check 5: Failure Type Logging
- **File**: `backend/app/core/search_client.py:35`
  ```python
  print(f"❌ Tavily search failed: {e}")
  ```
- **Status**: FAIL - Generic exception, no distinction between:
  - Network timeout
  - API key invalid
  - Rate limit exceeded
  - Service down
  - Query returned 0 results

### ❌ Check 6: Task Continues on Failure
- **File**: `backend/app/services/master_agent_service.py:49-61`
- **Issue**: Tool returns "검색 결과가 없습니다." but doesn't indicate failure vs no-results
- **Status**: PARTIAL - Task continues but with misleading message

---

## Audit Score: 2/6 → WEB_SEARCH_UNRELIABLE

**Recommendation**: Implement degraded mode

---

## Design Solution

### 1. Enhanced Tavily Client with Failure Tracking

**File**: `backend/app/core/search_client.py`

**Current**:
```python
def search(self, query: str, **kwargs):
    if not self.client:
        return []
    try:
        result = self.client.search(query=query, **kwargs)
        return result.get("results", [])
    except Exception as e:
        print(f"❌ Tavily search failed: {e}")
        return []
```

**Proposed**:
```python
from enum import Enum
from typing import Optional, List, Dict
import httpx

class SearchStatus(Enum):
    SUCCESS = "success"
    NO_RESULTS = "no_results"
    API_KEY_MISSING = "api_key_missing"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNKNOWN_ERROR = "unknown_error"

class SearchResult:
    status: SearchStatus
    results: List[Dict]
    error_message: Optional[str]
    
    def is_success(self) -> bool:
        return self.status == SearchStatus.SUCCESS
    
    def is_degraded(self) -> bool:
        return self.status != SearchStatus.SUCCESS

class TavilyClient:
    TIMEOUT_SECONDS = 10
    
    def search(self, query: str, max_results: int = 5, **kwargs) -> SearchResult:
        """
        Search with Tavily API.
        
        Returns:
            SearchResult with status and results
        """
        if not self.client:
            logger.warning("Tavily client not initialized (missing API key)")
            return SearchResult(
                status=SearchStatus.API_KEY_MISSING,
                results=[],
                error_message="TAVILY_API_KEY not configured"
            )
        
        try:
            logger.info(f"Tavily search request: '{query}' (max={max_results})")
            
            # Add timeout to SDK call (if supported)
            # Note: TavilySDK may not support timeout directly,
            # may need to wrap in asyncio.wait_for() if async version exists
            result = self.client.search(
                query=query,
                max_results=max_results,
                **kwargs
            )
            
            results_list = result.get("results", [])
            
            if not results_list:
                logger.info(f"Tavily returned 0 results for: '{query}'")
                return SearchResult(
                    status=SearchStatus.NO_RESULTS,
                    results=[],
                    error_message=None
                )
            
            logger.info(f"Tavily returned {len(results_list)} results")
            return SearchResult(
                status=SearchStatus.SUCCESS,
                results=results_list,
                error_message=None
            )
            
        except httpx.TimeoutException:
            logger.error(f"Tavily search timeout after {self.TIMEOUT_SECONDS}s: {query}")
            return SearchResult(
                status=SearchStatus.TIMEOUT,
                results=[],
                error_message=f"Search timed out after {self.TIMEOUT_SECONDS}s"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("Tavily rate limit exceeded")
                return SearchResult(
                    status=SearchStatus.RATE_LIMITED,
                    results=[],
                    error_message="Rate limit exceeded"
                )
            else:
                logger.error(f"Tavily HTTP error {e.response.status_code}: {e}")
                return SearchResult(
                    status=SearchStatus.NETWORK_ERROR,
                    results=[],
                    error_message=str(e)
                )
        except Exception as e:
            logger.error(f"Tavily unknown error: {e}")
            return SearchResult(
                status=SearchStatus.UNKNOWN_ERROR,
                results=[],
                error_message=str(e)
            )
```

### 2. Degraded Mode in Tool

**File**: `backend/app/services/master_agent_service.py`

**Current**:
```python
@tool
def web_search_intelligence_tool(query: str) -> str:
    client = TavilyClient()
    results = client.search(query, max_results=5)
    if not results:
        return "검색 결과가 없습니다."
    # ...
```

**Proposed**:
```python
from app.core.search_client import TavilyClient, SearchStatus

@tool
def web_search_intelligence_tool(query: str) -> str:
    """
    웹 검색을 통해 최신 정보를 수집하고 Fact로 기록합니다.
    
    Degraded Mode: Tavily 실패 시에도 작업 계속 진행.
    """
    client = TavilyClient()
    search_result = client.search(query, max_results=5)
    
    # Record search attempt (for monitoring)
    logger.info(
        "Web search executed",
        query=query,
        status=search_result.status.value,
        result_count=len(search_result.results)
    )
    
    if search_result.is_degraded():
        # Degraded mode - inform LLM but don't fail
        if search_result.status == SearchStatus.NO_RESULTS:
            return f"[검색 완료] '{query}'에 대한 검색 결과가 없습니다. 기존 지식을 바탕으로 답변하세요."
        else:
            return (
                f"[웹 검색 사용 불가] 외부 검색 서비스에 접근할 수 없습니다 "
                f"(사유: {search_result.error_message}). "
                f"기존 지식 그래프와 대화 맥락만을 바탕으로 답변하세요."
            )
    
    # Success - format results
    formatted = []
    for idx, res in enumerate(search_result.results, 1):
        title = res.get("title", "Untitled")
        url = res.get("url", "")
        snippet = res.get("content", "")[:200]
        formatted.append(f"{idx}. **{title}**\n   URL: {url}\n   {snippet}...")
    
    return "\n\n".join(formatted)
```

### 3. Event Logging for Monitoring

**New Function** in `search_client.py`:
```python
async def log_search_event(
    query: str, 
    status: SearchStatus, 
    result_count: int, 
    error: Optional[str] = None
):
    """
    Log search event to Redis for monitoring/dashboard.
    
    Event schema:
    {
      "type": "web_search",
      "query": "...",
      "status": "success" | "no_results" | "timeout" | ...,
      "result_count": 5,
      "error_message": "...",
      "timestamp": "2026-01-24T14:00:00Z"
    }
    """
    event = {
        "type": "web_search",
        "query": query,
        "status": status.value,
        "result_count": result_count,
        "error_message": error,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Push to Redis list (with max length to prevent bloat)
    await redis_client.lpush("events:web_search", json.dumps(event))
    await redis_client.ltrim("events:web_search", 0, 999)  # Keep last 1000 events
```

---

## Degraded Mode Behavior Matrix

| Tavily Status | Result Count | Action | LLM Context |
|---------------|--------------|--------|-------------|
| SUCCESS | >0 | Use results | Full search results |
| NO_RESULTS | 0 | Continue | "No results, use existing knowledge" |
| API_KEY_MISSING | 0 | Continue | "Search unavailable, use knowledge graph" |
| NETWORK_ERROR | 0 | Continue | "Search service down, use knowledge graph" |
| TIMEOUT | 0 | Continue | "Search timeout, use knowledge graph" |
| RATE_LIMITED | 0 | Continue | "Search rate limited, use knowledge graph" |

**Key Principle**: Task NEVER fails due to Tavily. LLM receives context about search status.

---

## Monitoring Dashboard Signals

### Metrics to Track
- `web_search_total{status}` - Count of searches by status
- `web_search_success_rate` - Percentage of successful searches
- `web_search_avg_results` - Average result count when successful
- `web_search_timeout_rate` - Percentage of timeouts

### Alerts (Non-Automated)
- **Warning**: `web_search_success_rate < 50%` for last 1 hour
- **Critical**: `web_search_success_rate < 10%` for last 1 hour
- **Info**: API key missing (one-time alert)

### Dashboard View
```
📊 Tavily Web Search Health (Last 24h)

Success:     45 (90%)
No Results:   3 (6%)
Timeout:      1 (2%)
Error:        1 (2%)

Avg Results: 4.2
Avg Latency: 1.2s
```

---

## Implementation Checklist

- [ ] Add `SearchStatus` enum to `search_client.py`
- [ ] Add `SearchResult` dataclass
- [ ] Update `TavilyClient.search()` to return `SearchResult`
- [ ] Add timeout configuration (default 10s)
- [ ] Add comprehensive error classification
- [ ] Update `web_search_intelligence_tool()` to handle degraded mode
- [ ] Add `log_search_event()` function
- [ ] Add Redis event stream for search attempts
- [ ] Update master agent prompt to handle "[웹 검색 사용 불가]" message
- [ ] Add monitoring dashboard query

---

## Testing Requirements

### Unit Tests
1. **Success Case**:
   ```python
   result = client.search("DeepSeek V3")
   assert result.status == SearchStatus.SUCCESS
   assert len(result.results) > 0
   ```

2. **No Results**:
   ```python
   result = client.search("asdfqwerzxcv12345")
   assert result.status == SearchStatus.NO_RESULTS
   assert result.results == []
   ```

3. **Missing API Key**:
   ```python
   with patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
       client = TavilyClient()
       result = client.search("test")
       assert result.status == SearchStatus.API_KEY_MISSING
   ```

4. **Timeout**:
   ```python
   with patch("httpx.Client.post", side_effect=httpx.TimeoutException):
       result = client.search("test")
       assert result.status == SearchStatus.TIMEOUT
   ```

### Integration Tests
1. **Tool Returns Degraded Message**:
   ```python
   with patch("TavilyClient.search", return_value=SearchResult(
       status=SearchStatus.TIMEOUT, results=[], error_message="Timeout"
   )):
       response = web_search_intelligence_tool("test")
       assert "[웹 검색 사용 불가]" in response
   ```

2. **Master Agent Handles Degraded Mode**:
   - Trigger web search with mocked timeout
   - Verify master agent generates response anyway
   - Verify response quality (may be lower but still useful)

---

## Breaking Changes

**Minimal**:
- `TavilyClient.search()` return type changes from `List[Dict]` to `SearchResult`

**Mitigation**:
- Only one caller: `web_search_intelligence_tool` in `master_agent_service.py`
- Update that single location

---

## References

- `backend/app/core/search_client.py` - Tavily client implementation
- `backend/app/services/master_agent_service.py` - Web search tool
- [MODEL_STRATEGY.md](./MODEL_STRATEGY.md) - RAG failure → model stays fixed
- [DASHBOARD_SIGNALS.md](./DASHBOARD_SIGNALS.md) - Monitoring signals
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md) - Event logging schema

---

## Compliance with User Requirements

✅ **Tavily 호출 코드 존재** - search_client.py  
✅ **TAVILY_API_KEY 로딩** - config.py (optional)  
❌ **실제 요청 발생 확인** - 로깅 추가 필요  
❌ **Timeout 설정** - 10s 추가  
❌ **실패 유형 구분 로깅** - SearchStatus 추가  
✅ **실패/0건 시 태스크 계속** - Degraded mode 구현  
✅ **이벤트 기록** - log_search_event()

**Audit Score after Implementation**: 6/6 → WEB_SEARCH_RELIABLE

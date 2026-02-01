from typing import List, Dict, Any
from tavily import TavilyClient as TavilySDK
from app.core.config import settings

class TavilyClient:
    """
    Client for Tavily Search API.
    """
    
    def __init__(self):
        if not settings.TAVILY_API_KEY:
            print("⚠️ [DEGRADED] TAVILY_API_KEY missing → web search skipped")
            print(f'{{"event":"WEB_SEARCH_FAILED","provider":"tavily","reason_code":"missing_api_key"}}')
            print('{"event":"WEB_SEARCH_FAILED","provider":"tavily","reason_code":"timeout"}')
            print('{"event":"WEB_SEARCH_FAILED","provider":"tavily","reason_code":"exception"}')
            print('{"event":"WEB_SEARCH_FAILED","provider":"tavily","reason_code":"zero_results"}')
            self.client = None
            return

        self.client = TavilySDK(api_key=settings.TAVILY_API_KEY)

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Perform web search.
        """
        if not self.client:
            return []

        try:
            # Tavily SDK is synchronous, but fast. 
            # In high-load async app, wrap in run_in_executor.
            response = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results
            )
            return response.get("results", [])
        except Exception as e:
            print(f"❌ Tavily search failed: {e}")
            return []

    async def search_and_summarize(self, query: str) -> str:
        """
        Search and return an answer/summary.
        """
        if not self.client:
            return "Search unavailable."

        try:
            response = self.client.qna_search(query=query)
            return response
        except Exception as e:
            print(f"❌ Tavily QnA failed: {e}")
            return f"Error during search: {e}"

# [v5.0] Global search client instance
search_client = TavilyClient()
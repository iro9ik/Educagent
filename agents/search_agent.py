"""
Search Agent — fetches information from the internet via DuckDuckGo.
Only activated when search toggle is ON.
"""

from agents.base import BaseAgent

try:
    from langchain_community.tools import DuckDuckGoSearchRun
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False


class SearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Search Agent",
            system_prompt=(
                "You are an internet research assistant. "
                "Summarize search results clearly and concisely. "
                "Focus on factual, educational content relevant to the query."
            ),
        )
        self._search_tool = DuckDuckGoSearchRun() if SEARCH_AVAILABLE else None

    def run(self, query: str, **kwargs) -> dict:
        """
        Perform an internet search and return summarized results.
        Returns {raw_results: str, summary: str}.
        """
        if not SEARCH_AVAILABLE or self._search_tool is None:
            return {
                "raw_results": "",
                "summary": "Search functionality is not available (missing duckduckgo-search).",
            }

        try:
            raw_results = self._search_tool.invoke(query)

            # Use LLM to summarize search results
            prompt = (
                f"Summarize the following internet search results for the query: '{query}'\n\n"
                f"Search Results:\n{raw_results}\n\n"
                "Provide a concise, factual summary focusing on educational content."
            )
            summary = super().run(prompt)

            return {
                "raw_results": raw_results,
                "summary": summary,
            }
        except Exception as e:
            return {
                "raw_results": "",
                "summary": f"Search failed: {str(e)}",
            }


search_agent = SearchAgent()

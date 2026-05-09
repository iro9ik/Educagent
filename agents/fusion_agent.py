"""
Fusion Agent — combines outputs from RAG and Search, filters for relevance.
"""

from agents.base import BaseAgent


class FusionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Fusion Agent",
            system_prompt=(
                "You are an information fusion specialist. Your job is to:\n"
                "1. Combine information from multiple sources (documents and web search)\n"
                "2. Remove duplicate or redundant information\n"
                "3. Rank information by relevance to the query\n"
                "4. Create a unified, coherent context\n"
                "5. Note the source of each piece of information\n\n"
                "Output a clean, well-organized synthesis of all available information."
            ),
        )

    def run(
        self,
        query: str,
        rag_context: str = "",
        search_context: str = "",
        **kwargs,
    ) -> str:
        """
        Merge RAG and Search outputs into a unified context.
        """
        parts = []

        if rag_context:
            parts.append(f"**Document Sources (RAG):**\n{rag_context}")

        if search_context:
            parts.append(f"**Internet Search Results:**\n{search_context}")

        if not parts:
            return "No information available to fuse."

        combined = "\n\n" + "\n\n".join(parts)

        prompt = (
            f"Query: {query}\n\n"
            f"Sources:\n{combined}\n\n"
            "Fuse these sources into a single, coherent, well-organized context. "
            "Remove duplicates, rank by relevance, and preserve source attributions."
        )

        return super().run(prompt)


fusion_agent = FusionAgent()

"""
Thinking Agent — performs structured reasoning and analysis.
Only activated when thinking toggle is ON.
"""

from agents.base import BaseAgent


class ThinkingAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Thinking Agent",
            system_prompt=(
                "You are an analytical reasoning specialist. Your job is to:\n"
                "1. Analyze the provided information deeply\n"
                "2. Identify key concepts, relationships, and patterns\n"
                "3. Organize the information in a logical structure\n"
                "4. Highlight important distinctions and nuances\n"
                "5. Draw connections between different pieces of information\n\n"
                "Provide your analysis in a structured format with clear sections."
            ),
        )

    def run(self, query: str, context: str = "", **kwargs) -> str:
        """
        Perform structured reasoning on the provided context.
        Returns a reasoned analysis string.
        """
        prompt = (
            f"Query: {query}\n\n"
            f"Available Information:\n{context}\n\n"
            "Perform a thorough analysis:\n"
            "1. Identify the core concepts\n"
            "2. Analyze relationships between concepts\n"
            "3. Note any gaps or ambiguities\n"
            "4. Organize findings logically\n"
            "5. Provide a structured summary"
        )

        return super().run(prompt)


thinking_agent = ThinkingAgent()

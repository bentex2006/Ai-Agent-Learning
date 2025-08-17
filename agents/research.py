import asyncio
import json
from typing import Dict, Any, List, Optional

from .base import BaseAgent, AgentResponse
from config import settings


class ResearchAgent(BaseAgent):

    def __init__(self):
        config = settings.get_agent_config("research")
        super().__init__(config)
    
    async def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """Process research-related queries"""
        
        # Analyze the intent of the message
        intent_analysis = await self._analyze_intent(message)
        
        # Determine if web search is needed
        needs_search = self._needs_web_search(message, intent_analysis)
        
        tools_used = []
        search_results = ""
        
        # Perform web search if needed
        if needs_search and "web_search" in self.get_available_tools():
            search_results = await self._perform_research(message)
            tools_used.append("web_search")
        
        # Prepare the research prompt
        research_prompt = self._build_research_prompt(message, search_results, context)
        
        # Get conversation history for context
        conversation_history = self.conversation_context.get_recent_messages(5)
        
        # Build messages for LLM
        messages = []
        
        # Add conversation history if available
        for hist in conversation_history:
            messages.append({"role": "user", "content": hist["user"]})
            messages.append({"role": "assistant", "content": hist["assistant"]})
        
        # Add current query
        messages.append({"role": "user", "content": research_prompt})
        
        # Generate response
        try:
            response_content = await self._call_llm(messages)
            
            # Add to conversation context
            self.add_to_context(message, response_content)
            
            return AgentResponse(
                content=response_content,
                agent_name=self.name,
                tools_used=tools_used,
                confidence=0.8,
                reasoning=f"Research query processed with intent: {intent_analysis.get('intent', 'unknown')}",
                metadata={
                    "intent_analysis": intent_analysis,
                    "search_performed": needs_search,
                    "search_results_length": len(search_results)
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"I apologize, but I encountered an error while researching: {e}",
                agent_name=self.name,
                tools_used=tools_used,
                confidence=0.1,
                reasoning="Error occurred during research",
                metadata={"error": str(e)}
            )
    
    def can_handle(self, message: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Determine if this agent can handle the research query"""
        base_score = super().can_handle(message, context)
        
        message_lower = message.lower()
        research_keywords = [
            "research", "find", "search", "what is", "who is", "when did", "where is",
            "how many", "statistics", "data", "facts", "information", "explain",
            "tell me about", "learn about", "study", "analyze", "investigate",
            "compare", "contrast", "history", "background", "details", "source"
        ]
        
        keyword_score = 0
        for keyword in research_keywords:
            if keyword in message_lower:
                keyword_score += 0.2
        
        # Boost score for question words
        question_words = ["what", "who", "when", "where", "why", "how"]
        if any(word in message_lower for word in question_words):
            keyword_score += 0.3
        
        return min(base_score + keyword_score, 1.0)
    
    def _needs_web_search(self, message: str, intent_analysis: Dict[str, Any]) -> bool:
        """Determine if web search is needed for this query"""
        
        # Skip search for personal or opinion-based questions
        personal_indicators = ["i think", "my opinion", "what do you think", "personal", "yourself"]
        if any(indicator in message.lower() for indicator in personal_indicators):
            return False
        
        # Search for factual, current, or specific information requests
        search_indicators = [
            "current", "latest", "recent", "today", "now", "2024", "2025",
            "statistics", "data", "news", "price", "stock", "weather",
            "who is", "what is", "when did", "where is", "how many"
        ]
        
        if any(indicator in message.lower() for indicator in search_indicators):
            return True
        
        # Check intent analysis
        if intent_analysis.get("tools_needed") and "web_search" in intent_analysis["tools_needed"]:
            return True
        
        return False
    
    async def _perform_research(self, query: str) -> str:
        """Perform web search research"""
        try:
            search_result = await self.use_tool("web_search", query=query, max_results=5)
            
            if "error" in search_result:
                return f"Search error: {search_result['error']}"
            
            # Format search results
            results = search_result.get("results", [])
            formatted_results = []
            
            for i, result in enumerate(results[:3], 1):  # Limit to top 3 results
                formatted_results.append(
                    f"{i}. **{result.get('title', 'No title')}**\n"
                    f"   {result.get('snippet', 'No description')}\n"
                    f"   Source: {result.get('url', 'No URL')}\n"
                )
            
            return "\n".join(formatted_results) if formatted_results else "No search results found."
            
        except Exception as e:
            return f"Research error: {e}"
    
    def _build_research_prompt(self, message: str, search_results: str, context: Optional[Dict[str, Any]]) -> str:
        """Build the research prompt for the LLM"""
        
        prompt_parts = [
            f"Research Query: {message}\n"
        ]
        
        if search_results:
            prompt_parts.append(f"Web Search Results:\n{search_results}\n")
        
        if context:
            prompt_parts.append(f"Additional Context: {json.dumps(context, indent=2)}\n")
        
        prompt_parts.append(
            "Please provide a comprehensive, well-researched response. "
            "Include relevant facts, citations when possible, and acknowledge any limitations or uncertainties. "
            "Structure your response clearly with key points and conclusions."
        )
        
        return "\n".join(prompt_parts)
    
    async def fact_check(self, claim: str) -> AgentResponse:
        """Specialized method for fact-checking claims"""
        
        fact_check_prompt = f"""
        Please fact-check the following claim:
        "{claim}"
        
        Provide:
        1. Verification status (True/False/Partially True/Unverified)
        2. Supporting evidence or sources
        3. Any important context or nuances
        4. Confidence level in your assessment
        """
        
        # Perform search for verification
        search_results = await self._perform_research(f"fact check: {claim}")
        
        full_prompt = f"{fact_check_prompt}\n\nSearch Results:\n{search_results}"
        
        try:
            response = await self._call_llm([{"role": "user", "content": full_prompt}])
            
            return AgentResponse(
                content=response,
                agent_name=self.name,
                tools_used=["web_search", "fact_check"],
                confidence=0.9,
                reasoning="Specialized fact-checking analysis performed",
                metadata={"claim": claim, "verification_performed": True}
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"Unable to fact-check the claim due to error: {e}",
                agent_name=self.name,
                confidence=0.1,
                metadata={"error": str(e)}
            )
    
    async def comparative_analysis(self, topics: List[str]) -> AgentResponse:
        """Compare multiple topics or entities"""
        
        if len(topics) < 2:
            return AgentResponse(
                content="Comparative analysis requires at least two topics.",
                agent_name=self.name,
                confidence=0.1
            )
        
        # Research each topic
        research_data = {}
        for topic in topics:
            research_data[topic] = await self._perform_research(topic)
        
        comparison_prompt = f"""
        Please provide a detailed comparative analysis of the following topics:
        {', '.join(topics)}
        
        Research data:
        {json.dumps(research_data, indent=2)}
        
        Structure your comparison with:
        1. Key similarities
        2. Major differences  
        3. Pros and cons of each
        4. Summary and conclusions
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": comparison_prompt}])
            
            return AgentResponse(
                content=response,
                agent_name=self.name,
                tools_used=["web_search", "comparative_analysis"],
                confidence=0.85,
                reasoning="Comparative analysis with multi-topic research",
                metadata={"topics_compared": topics, "research_performed": True}
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"Error during comparative analysis: {e}",
                agent_name=self.name,
                confidence=0.1,
                metadata={"error": str(e)}
            )

import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from agents import ResearchAgent, CodeAgent, CreativeAgent, TaskAgent
from config import settings


@dataclass
class RoutingDecision:
    """Represents a routing decision with confidence scores"""
    agent_name: str
    confidence: float
    reasoning: str
    alternative_agents: List[Tuple[str, float]] = None


class AgentRouter:
    """Routes user messages to the most appropriate agent"""
    
    def __init__(self):
        # Initialize all agents
        self.agents = {
            "research": ResearchAgent(),
            "code": CodeAgent(),
            "creative": CreativeAgent(),
            "task": TaskAgent()
        }
        
        # Agent capability keywords for routing hints
        self.agent_keywords = {
            "research": [
                "search", "find", "research", "information", "facts", "data",
                "what is", "who is", "when", "where", "why", "how many",
                "statistics", "analysis", "study", "investigate", "compare"
            ],
            "code": [
                "code", "program", "script", "function", "debug", "fix",
                "python", "javascript", "java", "programming", "development",
                "algorithm", "implementation", "software", "app", "bug"
            ],
            "creative": [
                "create", "write", "story", "idea", "brainstorm", "creative",
                "content", "blog", "article", "poem", "design", "imagine",
                "innovative", "original", "artistic", "inspiration"
            ],
            "task": [
                "plan", "organize", "schedule", "manage", "project", "task",
                "timeline", "deadline", "coordinate", "prioritize", "workflow",
                "goal", "objective", "strategy", "breakdown", "milestone"
            ]
        }
        
        # Default fallback preferences
        self.fallback_order = ["research", "creative", "task", "code"]
    
    async def route_message(self, message: str, context: Optional[Dict] = None, 
                          preferred_agent: Optional[str] = None) -> RoutingDecision:
        """
        Route a message to the most appropriate agent.
        
        Args:
            message: User message to route
            context: Optional context information
            preferred_agent: Optional specific agent preference
            
        Returns:
            RoutingDecision with selected agent and confidence
        """
        
        # If a specific agent is preferred and available, use it
        if preferred_agent and preferred_agent in self.agents:
            return RoutingDecision(
                agent_name=preferred_agent,
                confidence=1.0,
                reasoning=f"User explicitly requested {preferred_agent} agent"
            )
        
        # Get confidence scores from all agents
        agent_scores = {}
        for agent_name, agent in self.agents.items():
            try:
                score = agent.can_handle(message, context)
                agent_scores[agent_name] = score
            except Exception as e:
                print(f"Error getting score from {agent_name}: {e}")
                agent_scores[agent_name] = 0.0
        
        # Add keyword-based scoring
        keyword_scores = self._calculate_keyword_scores(message)
        
        # Combine scores (70% agent confidence, 30% keyword matching)
        combined_scores = {}
        for agent_name in self.agents.keys():
            agent_score = agent_scores.get(agent_name, 0.0)
            keyword_score = keyword_scores.get(agent_name, 0.0)
            combined_scores[agent_name] = (agent_score * 0.7) + (keyword_score * 0.3)
        
        # Sort by confidence score
        sorted_agents = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        if not sorted_agents or sorted_agents[0][1] < 0.1:
            # No agent has confidence, use fallback
            selected_agent = self._get_fallback_agent(message)
            confidence = 0.5
            reasoning = f"No agent showed strong confidence, using fallback: {selected_agent}"
        else:
            selected_agent = sorted_agents[0][0]
            confidence = sorted_agents[0][1]
            reasoning = f"Selected based on highest confidence score: {confidence:.2f}"
        
        # Prepare alternative agents
        alternatives = [(name, score) for name, score in sorted_agents[1:3] if score > 0.1]
        
        return RoutingDecision(
            agent_name=selected_agent,
            confidence=confidence,
            reasoning=reasoning,
            alternative_agents=alternatives
        )
    
    def _calculate_keyword_scores(self, message: str) -> Dict[str, float]:
        """Calculate keyword-based routing scores"""
        message_lower = message.lower()
        scores = {}
        
        for agent_name, keywords in self.agent_keywords.items():
            score = 0.0
            for keyword in keywords:
                if keyword in message_lower:
                    score += 0.1
            
            # Normalize score (max 1.0)
            scores[agent_name] = min(score, 1.0)
        
        return scores
    
    def _get_fallback_agent(self, message: str) -> str:
        """Get fallback agent when no clear routing decision can be made"""
        message_lower = message.lower()
        
        # Simple heuristics for fallback
        if any(word in message_lower for word in ["what", "how", "why", "explain"]):
            return "research"
        elif any(word in message_lower for word in ["create", "write", "generate"]):
            return "creative"
        elif any(word in message_lower for word in ["plan", "organize", "schedule"]):
            return "task"
        else:
            return self.fallback_order[0]  # Default to research
    
    def get_agent(self, agent_name: str):
        """Get agent instance by name"""
        return self.agents.get(agent_name)
    
    def get_available_agents(self) -> Dict[str, Dict]:
        """Get information about all available agents"""
        agent_info = {}
        for name, agent in self.agents.items():
            agent_info[name] = agent.get_info()
        return agent_info
    
    def has_agent(self, agent_name: str) -> bool:
        """Check if an agent exists"""
        return agent_name in self.agents
    
    async def analyze_routing_patterns(self, conversation_history: List[Dict]) -> Dict:
        """Analyze routing patterns from conversation history"""
        if not conversation_history:
            return {"analysis": "No conversation history available"}
        
        # Simple analysis of which agents were used
        agent_usage = {}
        for entry in conversation_history:
            agent_used = entry.get("agent_used", "unknown")
            agent_usage[agent_used] = agent_usage.get(agent_used, 0) + 1
        
        total_messages = len(conversation_history)
        usage_percentages = {
            agent: (count / total_messages) * 100 
            for agent, count in agent_usage.items()
        }
        
        # Identify most and least used agents
        most_used = max(agent_usage.items(), key=lambda x: x[1]) if agent_usage else ("none", 0)
        least_used = min(agent_usage.items(), key=lambda x: x[1]) if agent_usage else ("none", 0)
        
        return {
            "total_messages": total_messages,
            "agent_usage": agent_usage,
            "usage_percentages": usage_percentages,
            "most_used_agent": most_used[0],
            "least_used_agent": least_used[0],
            "routing_diversity": len(agent_usage) / len(self.agents) * 100
        }
    
    async def suggest_better_routing(self, message: str, current_agent: str, 
                                   user_feedback: str) -> Optional[str]:
        """Suggest better routing based on user feedback"""
        
        if "wrong" in user_feedback.lower() or "incorrect" in user_feedback.lower():
            # Re-route without the current agent
            routing_decision = await self.route_message(message)
            
            # Get alternatives that aren't the current agent
            alternatives = routing_decision.alternative_agents or []
            for alt_agent, score in alternatives:
                if alt_agent != current_agent and score > 0.3:
                    return alt_agent
            
            # If no good alternatives, try fallback
            fallback = self._get_fallback_agent(message)
            if fallback != current_agent:
                return fallback
        
        return None
    
    def update_routing_weights(self, message: str, chosen_agent: str, 
                             user_satisfaction: float):
        """Update routing weights based on user satisfaction (future enhancement)"""
        # This would be implemented to learn from user feedback
        # For now, it's a placeholder for future machine learning integration
        pass
    
    def get_routing_explanation(self, message: str) -> Dict[str, Any]:
        """Get detailed explanation of routing decision"""
        
        # Get scores from all agents
        agent_scores = {}
        explanations = {}
        
        for agent_name, agent in self.agents.items():
            try:
                score = agent.can_handle(message)
                agent_scores[agent_name] = score
                
                # Generate explanation based on agent capabilities
                capabilities = agent.capabilities
                explanations[agent_name] = {
                    "score": score,
                    "capabilities": capabilities,
                    "reasoning": f"Score based on {len(capabilities)} relevant capabilities"
                }
                
            except Exception as e:
                agent_scores[agent_name] = 0.0
                explanations[agent_name] = {
                    "score": 0.0,
                    "error": str(e)
                }
        
        # Add keyword analysis
        keyword_scores = self._calculate_keyword_scores(message)
        
        return {
            "message": message,
            "agent_scores": agent_scores,
            "keyword_scores": keyword_scores,
            "detailed_explanations": explanations,
            "recommended_agent": max(agent_scores.items(), key=lambda x: x[1])[0] if agent_scores else "research"
        }

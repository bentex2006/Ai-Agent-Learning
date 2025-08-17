import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .router import AgentRouter, RoutingDecision
from memory.storage import ConversationStorage
from memory.context import ConversationContext
from agents.base import AgentResponse
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CoordinatorResponse:
    """Response from the coordinator containing agent response and metadata"""
    content: str
    agent_used: str
    tools_used: List[str]
    confidence: float
    reasoning: str
    metadata: Dict[str, Any]
    session_id: str
    timestamp: datetime


class AgentCoordinator:
    """
    Coordinates interactions between multiple agents and manages conversation flow.
    """
    
    def __init__(self, settings_instance=None):
        self.settings = settings_instance or settings
        self.router = AgentRouter()
        self.storage = ConversationStorage()
        
        # Session management
        self.session_id = str(uuid.uuid4())
        self.conversation_context = ConversationContext(agent_name="coordinator")
        
        # Inter-agent communication
        self.agent_handoffs = {}
        self.multi_agent_tasks = {}
        
        logger.info(f"Agent Coordinator initialized with session: {self.session_id}")
    
    async def process_message(self, message: str, preferred_agent: Optional[str] = None, 
                            context: Optional[Dict[str, Any]] = None) -> CoordinatorResponse:
        """
        Process a user message through the multi-agent system.
        
        Args:
            message: User message to process
            preferred_agent: Optional specific agent to use
            context: Optional additional context
            
        Returns:
            CoordinatorResponse with agent response and metadata
        """
        timestamp = datetime.now()
        
        try:
            logger.info(f"Processing message: {message[:100]}...")
            
            # Route message to appropriate agent
            routing_decision = await self.router.route_message(
                message, context, preferred_agent
            )
            
            logger.info(f"Routed to {routing_decision.agent_name} agent (confidence: {routing_decision.confidence})")
            
            # Get the selected agent
            agent = self.router.get_agent(routing_decision.agent_name)
            if not agent:
                raise Exception(f"Agent {routing_decision.agent_name} not available")
            
            # Check if this requires multi-agent collaboration
            collaboration_needed = await self._check_collaboration_need(message, context)
            
            if collaboration_needed:
                # Handle multi-agent collaboration
                response = await self._handle_collaboration(message, routing_decision, context)
            else:
                # Single agent processing
                response = await agent.process_message(message, context)
            
            # Store conversation
            await self._store_conversation(message, response, routing_decision)
            
            # Update conversation context
            self.conversation_context.add_interaction(message, response.content)
            
            return CoordinatorResponse(
                content=response.content,
                agent_used=response.agent_name,
                tools_used=response.tools_used,
                confidence=response.confidence,
                reasoning=response.reasoning or routing_decision.reasoning,
                metadata={
                    **response.metadata,
                    "routing_decision": {
                        "selected_agent": routing_decision.agent_name,
                        "confidence": routing_decision.confidence,
                        "alternatives": routing_decision.alternative_agents
                    },
                    "collaboration_used": collaboration_needed,
                    "session_id": self.session_id
                },
                session_id=self.session_id,
                timestamp=timestamp
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
            # Return error response
            return CoordinatorResponse(
                content=f"I apologize, but I encountered an error while processing your request: {str(e)}",
                agent_used="coordinator",
                tools_used=[],
                confidence=0.1,
                reasoning="Error during message processing",
                metadata={"error": str(e)},
                session_id=self.session_id,
                timestamp=timestamp
            )
    
    async def _check_collaboration_need(self, message: str, context: Optional[Dict]) -> bool:
        """Check if the message requires multi-agent collaboration"""
        
        # Simple heuristics for collaboration detection
        collaboration_indicators = [
            "research and write", "analyze and create", "plan and implement",
            "compare and design", "investigate and report", "study and develop"
        ]
        
        message_lower = message.lower()
        
        # Check for explicit collaboration requests
        if any(indicator in message_lower for indicator in collaboration_indicators):
            return True
        
        # Check for multi-domain requests
        domains = ["research", "code", "creative", "task", "plan", "write", "analyze", "implement"]
        domain_count = sum(1 for domain in domains if domain in message_lower)
        
        if domain_count >= 2:
            return True
        
        # Check message complexity (longer messages more likely to need collaboration)
        if len(message.split()) > 50:
            return True
        
        return False
    
    async def _handle_collaboration(self, message: str, primary_routing: RoutingDecision, 
                                  context: Optional[Dict]) -> AgentResponse:
        """Handle multi-agent collaboration for complex requests"""
        
        logger.info("Initiating multi-agent collaboration")
        
        try:
            # Get primary agent
            primary_agent = self.router.get_agent(primary_routing.agent_name)
            
            # Identify secondary agents based on message content
            secondary_agents = await self._identify_secondary_agents(message, primary_routing.agent_name)
            
            # Create collaboration plan
            collaboration_plan = await self._create_collaboration_plan(
                message, primary_routing.agent_name, secondary_agents
            )
            
            logger.info(f"Collaboration plan: {collaboration_plan}")
            
            # Execute collaboration steps
            collaboration_results = {}
            
            for step in collaboration_plan.get("steps", []):
                agent_name = step.get("agent")
                task = step.get("task")
                
                if agent_name and task:
                    agent = self.router.get_agent(agent_name)
                    if agent:
                        step_result = await agent.process_message(task, context)
                        collaboration_results[agent_name] = step_result
                        logger.info(f"Completed step with {agent_name} agent")
            
            # Synthesize results
            synthesis_response = await self._synthesize_collaboration_results(
                message, collaboration_results, primary_agent
            )
            
            return synthesis_response
            
        except Exception as e:
            logger.error(f"Error in collaboration: {e}")
            
            # Fallback to primary agent
            primary_agent = self.router.get_agent(primary_routing.agent_name)
            return await primary_agent.process_message(message, context)
    
    async def _identify_secondary_agents(self, message: str, primary_agent: str) -> List[str]:
        """Identify which secondary agents should be involved"""
        
        secondary_agents = []
        message_lower = message.lower()
        
        # Agent capability mapping
        capability_keywords = {
            "research": ["research", "find", "information", "data", "facts", "search"],
            "code": ["code", "program", "implement", "development", "software"],
            "creative": ["create", "write", "design", "creative", "content", "idea"],
            "task": ["plan", "organize", "manage", "schedule", "coordinate"]
        }
        
        for agent_name, keywords in capability_keywords.items():
            if agent_name != primary_agent:
                if any(keyword in message_lower for keyword in keywords):
                    secondary_agents.append(agent_name)
        
        # Limit to 2 secondary agents to avoid complexity
        return secondary_agents[:2]
    
    async def _create_collaboration_plan(self, message: str, primary_agent: str, 
                                       secondary_agents: List[str]) -> Dict[str, Any]:
        """Create a plan for multi-agent collaboration"""
        
        # Simple collaboration plan based on agent types
        steps = []
        
        # Add secondary agent steps first (preparation)
        for i, agent in enumerate(secondary_agents):
            if agent == "research":
                steps.append({
                    "agent": agent,
                    "task": f"Research background information related to: {message}",
                    "order": i + 1
                })
            elif agent == "task":
                steps.append({
                    "agent": agent,
                    "task": f"Create an implementation plan for: {message}",
                    "order": i + 1
                })
            elif agent == "code":
                steps.append({
                    "agent": agent,
                    "task": f"Analyze technical requirements for: {message}",
                    "order": i + 1
                })
            elif agent == "creative":
                steps.append({
                    "agent": agent,
                    "task": f"Generate creative concepts for: {message}",
                    "order": i + 1
                })
        
        # Add primary agent step last (synthesis)
        steps.append({
            "agent": primary_agent,
            "task": f"Synthesize information and provide comprehensive response to: {message}",
            "order": len(steps) + 1
        })
        
        return {
            "primary_agent": primary_agent,
            "secondary_agents": secondary_agents,
            "steps": steps,
            "collaboration_type": "sequential"
        }
    
    async def _synthesize_collaboration_results(self, original_message: str, 
                                              collaboration_results: Dict[str, AgentResponse],
                                              primary_agent) -> AgentResponse:
        """Synthesize results from multiple agents into a cohesive response"""
        
        # Prepare synthesis context
        synthesis_context = {
            "original_message": original_message,
            "collaboration_results": {}
        }
        
        # Collect results from each agent
        for agent_name, result in collaboration_results.items():
            synthesis_context["collaboration_results"][agent_name] = {
                "content": result.content,
                "tools_used": result.tools_used,
                "confidence": result.confidence
            }
        
        # Create synthesis prompt
        synthesis_prompt = f"""
        Original request: "{original_message}"
        
        I've gathered information from multiple specialized agents:
        
        {json.dumps(synthesis_context["collaboration_results"], indent=2)}
        
        Please provide a comprehensive, well-integrated response that synthesizes all this information
        to fully address the original request. Ensure the response is coherent, complete, and
        acknowledges the contributions from different perspectives.
        """
        
        try:
            # Use primary agent to synthesize
            synthesis_response = await primary_agent.process_message(synthesis_prompt)
            
            # Combine tool usage from all agents
            all_tools_used = []
            for result in collaboration_results.values():
                all_tools_used.extend(result.tools_used)
            
            # Update response metadata
            synthesis_response.tools_used = list(set(all_tools_used))
            synthesis_response.metadata["collaboration_synthesis"] = True
            synthesis_response.metadata["agents_involved"] = list(collaboration_results.keys())
            
            return synthesis_response
            
        except Exception as e:
            logger.error(f"Error in synthesis: {e}")
            
            # Fallback: combine responses manually
            combined_content = f"Based on analysis from multiple agents:\n\n"
            
            for agent_name, result in collaboration_results.items():
                combined_content += f"**{agent_name.title()} Agent Insights:**\n{result.content}\n\n"
            
            return AgentResponse(
                content=combined_content,
                agent_name="coordinator",
                tools_used=list(set(all_tools_used)),
                confidence=0.7,
                reasoning="Multi-agent collaboration with manual synthesis",
                metadata={"collaboration_synthesis": True, "agents_involved": list(collaboration_results.keys())}
            )
    
    async def _store_conversation(self, message: str, response: AgentResponse, 
                                routing_decision: RoutingDecision):
        """Store conversation in persistent storage"""
        
        try:
            conversation_entry = {
                "session_id": self.session_id,
                "timestamp": datetime.now().isoformat(),
                "user_message": message,
                "agent_response": response.content,
                "agent_used": response.agent_name,
                "tools_used": response.tools_used,
                "confidence": response.confidence,
                "routing_confidence": routing_decision.confidence,
                "metadata": response.metadata
            }
            
            await self.storage.store_conversation(conversation_entry)
            
        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
    
    def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        try:
            return self.storage.get_recent_conversations(self.session_id, limit)
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return []
    
    def clear_history(self):
        """Clear conversation history for current session"""
        try:
            self.storage.clear_session(self.session_id)
            self.conversation_context = ConversationContext(agent_name="coordinator")
            logger.info(f"Cleared history for session {self.session_id}")
        except Exception as e:
            logger.error(f"Error clearing history: {e}")
    
    def get_available_agents(self) -> Dict[str, Dict]:
        """Get information about all available agents"""
        return self.router.get_available_agents()
    
    def has_agent(self, agent_name: str) -> bool:
        """Check if an agent is available"""
        return self.router.has_agent(agent_name)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        try:
            history = self.get_conversation_history(100)  # Get more for stats
            
            return {
                "session_id": self.session_id,
                "active_agents": list(self.router.agents.keys()),
                "total_messages": len(history),
                "memory_usage": len(self.conversation_context.get_recent_messages()),
                "last_activity": history[0]["timestamp"] if history else None,
                "agent_usage_stats": self._calculate_agent_usage_stats(history)
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "session_id": self.session_id,
                "active_agents": list(self.router.agents.keys()),
                "total_messages": 0,
                "memory_usage": 0,
                "error": str(e)
            }
    
    def _calculate_agent_usage_stats(self, history: List[Dict]) -> Dict[str, int]:
        """Calculate agent usage statistics from history"""
        stats = {}
        for entry in history:
            agent = entry.get("agent_used", "unknown")
            stats[agent] = stats.get(agent, 0) + 1
        return stats
    
    async def hand_off_to_agent(self, agent_name: str, message: str, 
                              context: Optional[Dict] = None) -> CoordinatorResponse:
        """Explicitly hand off a conversation to a specific agent"""
        
        logger.info(f"Explicit hand-off to {agent_name} agent")
        
        return await self.process_message(message, preferred_agent=agent_name, context=context)
    
    async def get_agent_recommendations(self, message: str) -> Dict[str, Any]:
        """Get recommendations for which agent to use"""
        
        routing_explanation = self.router.get_routing_explanation(message)
        
        return {
            "message": message,
            "recommended_agent": routing_explanation["recommended_agent"],
            "agent_scores": routing_explanation["agent_scores"],
            "explanations": routing_explanation["detailed_explanations"],
            "routing_confidence": max(routing_explanation["agent_scores"].values()) if routing_explanation["agent_scores"] else 0.0
        }

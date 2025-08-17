import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import deque
from dataclasses import dataclass, asdict

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ContextEntry:
    """Represents a single context entry"""
    timestamp: str
    user_message: str
    assistant_response: str
    agent_name: str
    context_type: str = "conversation"
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ConversationContext:
    """Manages conversation context and memory for agents"""
    
    def __init__(self, agent_name: str, max_memory_size: Optional[int] = None):
        self.agent_name = agent_name
        self.max_memory_size = max_memory_size or settings.max_conversation_history
        
        # Recent conversation memory (FIFO queue)
        self.recent_memory = deque(maxlen=self.max_memory_size)
        
        # Topic tracking
        self.current_topics = set()
        self.topic_history = []
        
        # Context metadata
        self.context_metadata = {
            "created_at": datetime.now().isoformat(),
            "agent_name": agent_name,
            "total_interactions": 0,
            "last_activity": None
        }
        
        # Conversation state
        self.conversation_state = {
            "current_task": None,
            "user_preferences": {},
            "active_context": {},
            "conversation_mode": "general"
        }
        
        logger.debug(f"Conversation context initialized for {agent_name}")
    
    def add_interaction(self, user_message: str, assistant_response: str, 
                       context_type: str = "conversation", metadata: Optional[Dict[str, Any]] = None):
        """Add a new interaction to the context"""
        
        try:
            entry = ContextEntry(
                timestamp=datetime.now().isoformat(),
                user_message=user_message,
                assistant_response=assistant_response,
                agent_name=self.agent_name,
                context_type=context_type,
                metadata=metadata or {}
            )
            
            # Add to recent memory
            self.recent_memory.append(entry)
            
            # Update metadata
            self.context_metadata["total_interactions"] += 1
            self.context_metadata["last_activity"] = entry.timestamp
            
            # Extract and track topics
            self._extract_topics(user_message)
            
            # Update conversation state
            self._update_conversation_state(user_message, assistant_response)
            
            logger.debug(f"Added interaction to context for {self.agent_name}")
            
        except Exception as e:
            logger.error(f"Failed to add interaction to context: {e}")
    
    def get_recent_messages(self, count: int = 5) -> List[Dict[str, str]]:
        """Get recent messages in a format suitable for LLM context"""
        
        try:
            recent_entries = list(self.recent_memory)[-count:] if self.recent_memory else []
            
            messages = []
            for entry in recent_entries:
                messages.append({
                    "user": entry.user_message,
                    "assistant": entry.assistant_response,
                    "timestamp": entry.timestamp,
                    "agent": entry.agent_name
                })
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get recent messages: {e}")
            return []
    
    def get_context_summary(self, max_length: int = 500) -> str:
        """Get a summary of the conversation context"""
        
        try:
            if not self.recent_memory:
                return "No conversation history available."
            
            # Get recent interactions
            recent_count = min(3, len(self.recent_memory))
            recent_entries = list(self.recent_memory)[-recent_count:]
            
            # Build summary
            summary_parts = []
            
            # Add basic info
            summary_parts.append(f"Conversation with {self.agent_name} agent")
            summary_parts.append(f"Total interactions: {self.context_metadata['total_interactions']}")
            
            # Add current topics
            if self.current_topics:
                topics_str = ", ".join(list(self.current_topics)[:5])
                summary_parts.append(f"Current topics: {topics_str}")
            
            # Add recent conversation snippets
            if recent_entries:
                summary_parts.append("Recent conversation:")
                for entry in recent_entries:
                    user_snippet = entry.user_message[:100] + "..." if len(entry.user_message) > 100 else entry.user_message
                    summary_parts.append(f"User: {user_snippet}")
                    
                    response_snippet = entry.assistant_response[:100] + "..." if len(entry.assistant_response) > 100 else entry.assistant_response
                    summary_parts.append(f"Assistant: {response_snippet}")
            
            # Add current task if any
            if self.conversation_state.get("current_task"):
                summary_parts.append(f"Current task: {self.conversation_state['current_task']}")
            
            full_summary = "\n".join(summary_parts)
            
            # Truncate if too long
            if len(full_summary) > max_length:
                full_summary = full_summary[:max_length - 3] + "..."
            
            return full_summary
            
        except Exception as e:
            logger.error(f"Failed to generate context summary: {e}")
            return "Error generating context summary."
    
    def _extract_topics(self, message: str):
        """Extract topics from user message"""
        
        try:
            # Simple topic extraction based on keywords
            # In a production system, you might use NLP libraries
            
            message_lower = message.lower()
            
            # Define topic keywords
            topic_keywords = {
                "programming": ["code", "program", "script", "development", "software", "algorithm"],
                "research": ["research", "study", "analyze", "information", "data", "facts"],
                "creative": ["create", "write", "design", "story", "creative", "idea"],
                "planning": ["plan", "organize", "schedule", "task", "project", "goal"],
                "technology": ["ai", "machine learning", "tech", "computer", "digital"],
                "business": ["business", "company", "market", "strategy", "finance"],
                "education": ["learn", "teach", "course", "study", "tutorial", "explain"],
                "science": ["science", "research", "experiment", "hypothesis", "theory"]
            }
            
            # Extract topics
            new_topics = set()
            for topic, keywords in topic_keywords.items():
                if any(keyword in message_lower for keyword in keywords):
                    new_topics.add(topic)
            
            # Update current topics (keep recent topics active)
            self.current_topics.update(new_topics)
            
            # Add to topic history with timestamp
            if new_topics:
                self.topic_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "topics": list(new_topics),
                    "message_snippet": message[:100]
                })
            
            # Keep topic history manageable
            if len(self.topic_history) > 50:
                self.topic_history = self.topic_history[-50:]
            
        except Exception as e:
            logger.error(f"Failed to extract topics: {e}")
    
    def _update_conversation_state(self, user_message: str, assistant_response: str):
        """Update conversation state based on interaction"""
        
        try:
            message_lower = user_message.lower()
            
            # Detect task-related conversations
            task_indicators = ["help me", "i need to", "can you", "please", "task", "project"]
            if any(indicator in message_lower for indicator in task_indicators):
                # Extract potential task
                if len(user_message) > 20:  # Substantial request
                    self.conversation_state["current_task"] = user_message[:200]
            
            # Detect user preferences
            preference_indicators = ["i prefer", "i like", "i don't like", "i want", "i need"]
            for indicator in preference_indicators:
                if indicator in message_lower:
                    # Store as preference (simplified)
                    pref_key = f"preference_{len(self.conversation_state['user_preferences'])}"
                    self.conversation_state["user_preferences"][pref_key] = {
                        "statement": user_message,
                        "timestamp": datetime.now().isoformat()
                    }
            
            # Detect conversation mode changes
            if any(word in message_lower for word in ["creative", "brainstorm", "idea"]):
                self.conversation_state["conversation_mode"] = "creative"
            elif any(word in message_lower for word in ["analyze", "research", "study"]):
                self.conversation_state["conversation_mode"] = "analytical"
            elif any(word in message_lower for word in ["plan", "organize", "task"]):
                self.conversation_state["conversation_mode"] = "planning"
            elif any(word in message_lower for word in ["code", "program", "debug"]):
                self.conversation_state["conversation_mode"] = "technical"
            
        except Exception as e:
            logger.error(f"Failed to update conversation state: {e}")
    
    def get_relevant_context(self, query: str, max_entries: int = 3) -> List[Dict[str, Any]]:
        """Get context entries relevant to a specific query"""
        
        try:
            if not self.recent_memory:
                return []
            
            query_lower = query.lower()
            relevant_entries = []
            
            # Score entries based on relevance
            for entry in self.recent_memory:
                score = 0
                
                # Check for keyword matches in user message
                user_words = entry.user_message.lower().split()
                query_words = query_lower.split()
                
                for query_word in query_words:
                    if len(query_word) > 3:  # Skip short words
                        for user_word in user_words:
                            if query_word in user_word or user_word in query_word:
                                score += 1
                
                # Check for keyword matches in assistant response
                assistant_words = entry.assistant_response.lower().split()
                for query_word in query_words:
                    if len(query_word) > 3:
                        for assistant_word in assistant_words:
                            if query_word in assistant_word or assistant_word in query_word:
                                score += 0.5
                
                if score > 0:
                    relevant_entries.append({
                        "entry": entry,
                        "relevance_score": score
                    })
            
            # Sort by relevance and recency
            relevant_entries.sort(key=lambda x: (x["relevance_score"], x["entry"].timestamp), reverse=True)
            
            # Return top entries
            result = []
            for item in relevant_entries[:max_entries]:
                entry = item["entry"]
                result.append({
                    "user_message": entry.user_message,
                    "assistant_response": entry.assistant_response,
                    "timestamp": entry.timestamp,
                    "relevance_score": item["relevance_score"],
                    "agent_name": entry.agent_name
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get relevant context: {e}")
            return []
    
    def get_conversation_statistics(self) -> Dict[str, Any]:
        """Get statistics about the conversation"""
        
        try:
            total_interactions = len(self.recent_memory)
            
            if total_interactions == 0:
                return {
                    "total_interactions": 0,
                    "agent_name": self.agent_name,
                    "status": "no_interactions"
                }
            
            # Calculate statistics
            first_interaction = self.recent_memory[0].timestamp if self.recent_memory else None
            last_interaction = self.recent_memory[-1].timestamp if self.recent_memory else None
            
            # Calculate average message length
            total_user_chars = sum(len(entry.user_message) for entry in self.recent_memory)
            total_assistant_chars = sum(len(entry.assistant_response) for entry in self.recent_memory)
            
            avg_user_message_length = total_user_chars / total_interactions
            avg_assistant_message_length = total_assistant_chars / total_interactions
            
            # Get topic distribution
            topic_counts = {}
            for topic in self.current_topics:
                # Count how many times each topic appears in history
                count = sum(1 for entry in self.topic_history if topic in entry.get("topics", []))
                topic_counts[topic] = count
            
            return {
                "total_interactions": total_interactions,
                "agent_name": self.agent_name,
                "first_interaction": first_interaction,
                "last_interaction": last_interaction,
                "avg_user_message_length": round(avg_user_message_length, 1),
                "avg_assistant_message_length": round(avg_assistant_message_length, 1),
                "current_topics": list(self.current_topics),
                "topic_distribution": topic_counts,
                "conversation_mode": self.conversation_state.get("conversation_mode", "general"),
                "current_task": self.conversation_state.get("current_task"),
                "user_preferences_count": len(self.conversation_state.get("user_preferences", {}))
            }
            
        except Exception as e:
            logger.error(f"Failed to get conversation statistics: {e}")
            return {"error": str(e)}
    
    def clear_context(self):
        """Clear all context data"""
        
        try:
            self.recent_memory.clear()
            self.current_topics.clear()
            self.topic_history.clear()
            
            # Reset conversation state
            self.conversation_state = {
                "current_task": None,
                "user_preferences": {},
                "active_context": {},
                "conversation_mode": "general"
            }
            
            # Update metadata
            self.context_metadata["total_interactions"] = 0
            self.context_metadata["last_activity"] = None
            
            logger.info(f"Cleared context for {self.agent_name}")
            
        except Exception as e:
            logger.error(f"Failed to clear context: {e}")
    
    def export_context(self) -> Dict[str, Any]:
        """Export context data for backup or analysis"""
        
        try:
            # Convert deque to list for JSON serialization
            recent_memory_list = [asdict(entry) for entry in self.recent_memory]
            
            return {
                "agent_name": self.agent_name,
                "context_metadata": self.context_metadata,
                "recent_memory": recent_memory_list,
                "current_topics": list(self.current_topics),
                "topic_history": self.topic_history,
                "conversation_state": self.conversation_state,
                "exported_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to export context: {e}")
            return {"error": str(e)}
    
    def import_context(self, context_data: Dict[str, Any]):
        """Import context data from backup"""
        
        try:
            # Clear existing context
            self.clear_context()
            
            # Import data
            self.context_metadata = context_data.get("context_metadata", self.context_metadata)
            
            # Import recent memory
            memory_data = context_data.get("recent_memory", [])
            for entry_dict in memory_data:
                entry = ContextEntry(**entry_dict)
                self.recent_memory.append(entry)
            
            # Import topics
            self.current_topics = set(context_data.get("current_topics", []))
            self.topic_history = context_data.get("topic_history", [])
            
            # Import conversation state
            self.conversation_state = context_data.get("conversation_state", self.conversation_state)
            
            logger.info(f"Imported context for {self.agent_name}")
            
        except Exception as e:
            logger.error(f"Failed to import context: {e}")
    
    def get_context_for_llm(self, include_topics: bool = True, 
                           include_state: bool = True) -> str:
        """Get formatted context string for LLM consumption"""
        
        try:
            context_parts = []
            
            # Add recent conversation
            recent_messages = self.get_recent_messages(3)
            if recent_messages:
                context_parts.append("Recent conversation:")
                for msg in recent_messages:
                    context_parts.append(f"User: {msg['user']}")
                    context_parts.append(f"Assistant: {msg['assistant']}")
            
            # Add current topics
            if include_topics and self.current_topics:
                topics_str = ", ".join(list(self.current_topics)[:5])
                context_parts.append(f"\nCurrent conversation topics: {topics_str}")
            
            # Add conversation state
            if include_state:
                if self.conversation_state.get("current_task"):
                    context_parts.append(f"\nCurrent task: {self.conversation_state['current_task']}")
                
                if self.conversation_state.get("conversation_mode") != "general":
                    context_parts.append(f"Conversation mode: {self.conversation_state['conversation_mode']}")
            
            return "\n".join(context_parts) if context_parts else ""
            
        except Exception as e:
            logger.error(f"Failed to get context for LLM: {e}")
            return ""

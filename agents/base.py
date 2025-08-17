import asyncio
import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

import requests
from pydantic import BaseModel

from config import AgentConfig, settings
from memory.context import ConversationContext
from tools import get_tool_by_name


class AgentResponse(BaseModel):
    """Response from an agent"""
    content: str
    agent_name: str
    tools_used: List[str] = []
    confidence: float = 0.0
    reasoning: Optional[str] = None
    metadata: Dict[str, Any] = {}


class BaseAgent(ABC):
    """Base class for all AI agents in the system"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name
        self.personality = config.personality
        self.capabilities = config.capabilities
        self.tools = [get_tool_by_name(tool_name) for tool_name in config.tools]
        
        # Initialize OpenRouter client
        self.openrouter_api_key = os.environ.get('OPENROUTER_API_KEY')
        if not self.openrouter_api_key:
            sys.exit('OPENROUTER_API_KEY environment variable must be set')
        
        # OpenRouter configuration
        self.model = settings.model_name
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        
        self.conversation_context = ConversationContext(agent_name=self.name)
    
    @abstractmethod
    async def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """Process a message and return a response"""
        pass
    
    def can_handle(self, message: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        Determine if this agent can handle the given message.
        Returns a confidence score between 0.0 and 1.0
        """
        # Default implementation based on keywords
        message_lower = message.lower()
        score = 0.0
        
        # Check for capability keywords
        for capability in self.capabilities:
            if capability.lower() in message_lower:
                score += 0.3
        
        # Check for tool-related keywords
        for tool in self.tools:
            if hasattr(tool, 'keywords'):
                for keyword in tool.keywords:
                    if keyword.lower() in message_lower:
                        score += 0.2
        
        return min(score, 1.0)
    
    async def _call_llm(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> str:
        """Call the OpenRouter LLM with the given messages"""
        try:
            # Prepare system message
            if not system_prompt:
                system_prompt = self.config.system_prompt
            
            # Add system message to the beginning
            formatted_messages = []
            if system_prompt:
                formatted_messages.append({"role": "system", "content": system_prompt})
            formatted_messages.extend(messages)
                
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            
            response = requests.post(self.openrouter_url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            raise Exception(f"Error calling LLM: {e}")
    
    async def _stream_llm(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Stream responses from the OpenRouter LLM"""
        try:
            if not system_prompt:
                system_prompt = self.config.system_prompt
            
            # Add system message to the beginning
            formatted_messages = []
            if system_prompt:
                formatted_messages.append({"role": "system", "content": system_prompt})
            formatted_messages.extend(messages)
                
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "stream": True
            }
            
            response = requests.post(self.openrouter_url, headers=headers, json=payload, stream=True)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        if line_str == 'data: [DONE]':
                            break
                        try:
                            data = json.loads(line_str[6:])
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    yield delta['content']
                        except json.JSONDecodeError:
                            continue
                    
        except Exception as e:
            yield f"Error streaming response: {e}"
    
    async def use_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Use a specific tool"""
        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    return await tool.execute(**kwargs)
                except Exception as e:
                    return {"error": f"Tool execution failed: {e}"}
        
        return {"error": f"Tool '{tool_name}' not available for {self.name} agent"}
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return [tool.name for tool in self.tools]
    
    def add_to_context(self, message: str, response: str):
        """Add interaction to conversation context"""
        self.conversation_context.add_interaction(message, response)
    
    def get_context_summary(self) -> str:
        """Get a summary of the conversation context"""
        return self.conversation_context.get_summary()
    
    def get_info(self) -> Dict[str, Any]:
        """Get information about this agent"""
        return {
            "name": self.name,
            "personality": self.personality,
            "capabilities": self.capabilities,
            "tools": self.get_available_tools(),
            "description": self.config.system_prompt[:200] + "..." if len(self.config.system_prompt) > 200 else self.config.system_prompt
        }
    
    async def _analyze_intent(self, message: str) -> Dict[str, Any]:
        """Analyze the intent of the user message"""
        analysis_prompt = f"""
        Analyze the following user message and determine:
        1. The main intent or goal
        2. What tools or capabilities might be needed
        3. The urgency or priority level (1-5)
        4. Any specific requirements or constraints
        
        Message: "{message}"
        
        Respond in JSON format with keys: intent, tools_needed, priority, requirements
        """
        
        try:
            response = await self._call_llm([
                {"role": "user", "content": analysis_prompt}
            ])
            
            # Try to parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "intent": "general_query",
                    "tools_needed": [],
                    "priority": 3,
                    "requirements": []
                }
                
        except Exception as e:
            return {
                "intent": "general_query",
                "tools_needed": [],
                "priority": 3,
                "requirements": [],
                "analysis_error": str(e)
            }
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', capabilities={self.capabilities})"

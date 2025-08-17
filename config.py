from dotenv import load_dotenv
import os
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

load_dotenv()

class AgentConfig(BaseModel):

    name: str
    personality: str
    capabilities: List[str]
    tools: List[str]
    temperature: float = 0.7
    max_tokens: int = 1000
    system_prompt: str = ""


class Settings(BaseSettings):

    
    # API Configuration
    openrouter_api_key: str = Field(..., env="OPENROUTER_API_KEY")
    model_name: str = "openai/gpt-oss-20b:free"  # OpenRouter free model
    
    # System Configuration
    max_conversation_history: int = 100
    memory_storage_path: str = "./data/memory"
    log_level: str = "INFO"
    
    # Agent Configuration
    enable_streaming: bool = True
    default_temperature: float = 0.7
    max_tokens: int = 1500
    
    # Tool Configuration
    web_search_enabled: bool = True
    file_operations_enabled: bool = True
    code_execution_enabled: bool = True
    
    # Security Settings
    safe_mode: bool = True
    allowed_file_extensions: List[str] = [".txt", ".md", ".py", ".js", ".json", ".csv"]
    max_file_size_mb: int = 10
    
    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
        'case_sensitive': False
    }
    
    @field_validator("openrouter_api_key")
    @classmethod
    def validate_api_key(cls, v):
        if not v or v == "your-api-key-here":
            raise ValueError("OPENROUTER_API_KEY must be set to a valid API key")
        return v
    
    @field_validator("memory_storage_path")
    @classmethod
    def create_storage_path(cls, v):
        os.makedirs(v, exist_ok=True)
        return v
    
    def get_agent_config(self, agent_name: str) -> AgentConfig:

        agent_configs = {
            "research": AgentConfig(
                name="research",
                personality="analytical, thorough, fact-focused",
                capabilities=["web_search", "data_analysis", "fact_checking", "research"],
                tools=["web_search", "file_ops"],
                temperature=0.3,
                system_prompt="""You are a Research Agent, an expert researcher and analyst. 
                Your personality is analytical, thorough, and fact-focused. You excel at:
                - Conducting comprehensive research on any topic
                - Finding and verifying factual information
                - Analyzing data and trends
                - Providing well-sourced, objective information
                - Breaking down complex topics into understandable parts
                
                Always cite sources when possible and acknowledge when information might be uncertain."""
            ),
            
            "code": AgentConfig(
                name="code",
                personality="precise, logical, solution-oriented",
                capabilities=["code_generation", "debugging", "code_review", "architecture"],
                tools=["code_exec", "file_ops"],
                temperature=0.2,
                system_prompt="""You are a Code Agent, an expert software engineer and programmer.
                Your personality is precise, logical, and solution-oriented. You excel at:
                - Writing clean, efficient, and well-documented code
                - Debugging and troubleshooting software issues
                - Code review and optimization suggestions
                - Explaining programming concepts clearly
                - Designing software architecture and patterns
                
                Always provide working code examples and explain your reasoning."""
            ),
            
            "creative": AgentConfig(
                name="creative",
                personality="imaginative, expressive, inspiring",
                capabilities=["content_creation", "brainstorming", "storytelling", "design"],
                tools=["file_ops"],
                temperature=0.9,
                system_prompt="""You are a Creative Agent, an expert in creative thinking and content creation.
                Your personality is imaginative, expressive, and inspiring. You excel at:
                - Generating creative ideas and concepts
                - Writing engaging content and stories
                - Brainstorming and ideation
                - Visual and design thinking
                - Helping overcome creative blocks
                
                Be bold, think outside the box, and inspire creativity in others."""
            ),
            
            "task": AgentConfig(
                name="task",
                personality="organized, efficient, goal-oriented",
                capabilities=["project_management", "planning", "coordination", "optimization"],
                tools=["file_ops"],
                temperature=0.5,
                system_prompt="""You are a Task Agent, an expert project manager and coordinator.
                Your personality is organized, efficient, and goal-oriented. You excel at:
                - Breaking down complex projects into manageable tasks
                - Creating detailed plans and timelines
                - Coordinating between different agents and resources
                - Optimizing workflows and processes
                - Tracking progress and identifying bottlenecks
                
                Always provide clear, actionable steps and maintain focus on objectives."""
            )
        }
        
        return agent_configs.get(agent_name, AgentConfig(
            name=agent_name,
            personality="helpful and knowledgeable",
            capabilities=["general_assistance"],
            tools=[],
            system_prompt="You are a helpful AI assistant."
        ))


# Global settings instance
settings = Settings()

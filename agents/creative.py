import asyncio
import json
import random
from typing import Dict, Any, List, Optional

from .base import BaseAgent, AgentResponse
from config import settings


class CreativeAgent(BaseAgent):

    def __init__(self):
        config = settings.get_agent_config("creative")
        super().__init__(config)
        
        # Creative domains
        self.creative_domains = [
            "writing", "storytelling", "poetry", "brainstorming", "ideation",
            "content_creation", "marketing", "design_thinking", "creative_problem_solving",
            "worldbuilding", "character_development", "plot_development"
        ]
        
        # Creative techniques
        self.techniques = [
            "mind_mapping", "free_writing", "word_association", "role_playing",
            "scenario_planning", "analogical_thinking", "lateral_thinking",
            "reverse_brainstorming", "six_thinking_hats", "scamper_method"
        ]
    
    async def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """Process creative requests"""
        
        # Analyze creative intent
        creative_analysis = await self._analyze_creative_intent(message)
        
        # Determine creative approach
        approach = creative_analysis.get("approach", "general_creative")
        domain = creative_analysis.get("domain", "general")
        
        tools_used = []
        
        # Handle file operations if needed for saving creative content
        if creative_analysis.get("needs_file_save", False) and "file_ops" in self.get_available_tools():
            tools_used.append("file_ops")
        
        # Build creative prompt based on the approach
        creative_prompt = self._build_creative_prompt(message, creative_analysis, context)
        
        # Get conversation history for creative context
        conversation_history = self.conversation_context.get_recent_messages(4)
        
        # Build messages for LLM
        messages = []
        
        # Add conversation history for creative continuity
        for hist in conversation_history:
            messages.append({"role": "user", "content": hist["user"]})
            messages.append({"role": "assistant", "content": hist["assistant"]})
        
        # Add current creative request
        messages.append({"role": "user", "content": creative_prompt})
        
        try:
            response_content = await self._call_llm(messages)
            
            # Enhance creative response with formatting
            formatted_response = self._format_creative_response(response_content, approach)
            
            # Add to conversation context
            self.add_to_context(message, formatted_response)
            
            return AgentResponse(
                content=formatted_response,
                agent_name=self.name,
                tools_used=tools_used,
                confidence=0.85,
                reasoning=f"Creative task processed using {approach} approach",
                metadata={
                    "creative_approach": approach,
                    "domain": domain,
                    "analysis": creative_analysis,
                    "creativity_level": creative_analysis.get("creativity_level", "medium")
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"I encountered an issue while working on your creative request: {e}",
                agent_name=self.name,
                tools_used=tools_used,
                confidence=0.1,
                reasoning="Error occurred during creative processing",
                metadata={"error": str(e)}
            )
    
    def can_handle(self, message: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Determine if this agent can handle the creative request"""
        base_score = super().can_handle(message, context)
        
        message_lower = message.lower()
        
        # Creative keywords
        creative_keywords = [
            "create", "write", "story", "poem", "idea", "brainstorm", "imagine",
            "design", "creative", "artistic", "innovative", "original", "unique",
            "inspiration", "concept", "theme", "character", "plot", "narrative",
            "content", "script", "dialogue", "scene", "chapter", "book", "novel"
        ]
        
        # Creative action words
        action_words = [
            "compose", "craft", "develop", "invent", "generate", "produce",
            "conceive", "formulate", "devise", "dream up", "come up with"
        ]
        
        # Creative output types
        output_types = [
            "blog post", "article", "essay", "story", "poem", "song", "script",
            "advertisement", "slogan", "tagline", "headline", "caption", "description"
        ]
        
        keyword_score = 0
        
        # Check for creative keywords
        for keyword in creative_keywords:
            if keyword in message_lower:
                keyword_score += 0.2
        
        # Check for action words
        for action in action_words:
            if action in message_lower:
                keyword_score += 0.25
        
        # Check for output types
        for output_type in output_types:
            if output_type in message_lower:
                keyword_score += 0.3
        
        # Boost for explicit creative requests
        creative_phrases = [
            "be creative", "think creatively", "creative ideas", "out of the box",
            "brainstorm", "come up with", "write a", "create a", "design a"
        ]
        
        if any(phrase in message_lower for phrase in creative_phrases):
            keyword_score += 0.4
        
        return min(base_score + keyword_score, 1.0)
    
    async def _analyze_creative_intent(self, message: str) -> Dict[str, Any]:
        """Analyze the creative intent of the user message"""
        
        intent_prompt = f"""
        Analyze this creative request and determine:
        1. Creative approach needed (storytelling, brainstorming, content_creation, ideation, problem_solving)
        2. Creative domain (writing, marketing, design, entertainment, business, etc.)
        3. Target audience or purpose
        4. Creativity level needed (low, medium, high, experimental)
        5. Format or structure requested
        6. Whether file saving might be needed
        
        Message: "{message}"
        
        Respond in JSON format.
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": intent_prompt}])
            
            # Try to parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                
                # Validate and set defaults
                analysis.setdefault("approach", "general_creative")
                analysis.setdefault("domain", "general")
                analysis.setdefault("creativity_level", "medium")
                analysis.setdefault("needs_file_save", False)
                
                return analysis
            
        except Exception as e:
            pass
        
        # Fallback analysis
        return {
            "approach": self._detect_creative_approach(message),
            "domain": self._detect_creative_domain(message),
            "creativity_level": "medium",
            "needs_file_save": "save" in message.lower() or "file" in message.lower()
        }
    
    def _detect_creative_approach(self, message: str) -> str:
        """Detect the type of creative approach needed"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["story", "narrative", "tale", "fiction"]):
            return "storytelling"
        elif any(word in message_lower for word in ["brainstorm", "ideas", "think", "concepts"]):
            return "brainstorming"
        elif any(word in message_lower for word in ["content", "blog", "article", "post", "copy"]):
            return "content_creation"
        elif any(word in message_lower for word in ["solve", "problem", "challenge", "solution"]):
            return "problem_solving"
        elif any(word in message_lower for word in ["design", "visual", "layout", "interface"]):
            return "design_thinking"
        else:
            return "general_creative"
    
    def _detect_creative_domain(self, message: str) -> str:
        """Detect the creative domain"""
        message_lower = message.lower()
        
        domain_keywords = {
            "writing": ["write", "story", "poem", "essay", "book", "novel", "article"],
            "marketing": ["marketing", "advertisement", "campaign", "brand", "promotion"],
            "entertainment": ["game", "movie", "show", "entertainment", "fun", "humor"],
            "business": ["business", "startup", "company", "product", "service"],
            "education": ["teaching", "learning", "course", "lesson", "tutorial"],
            "technology": ["app", "software", "tech", "digital", "platform"]
        }
        
        for domain, keywords in domain_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return domain
        
        return "general"
    
    def _build_creative_prompt(self, message: str, creative_analysis: Dict[str, Any], 
                             context: Optional[Dict[str, Any]]) -> str:
        """Build the creative prompt for the LLM"""
        
        approach = creative_analysis.get("approach", "general_creative")
        domain = creative_analysis.get("domain", "general")
        creativity_level = creative_analysis.get("creativity_level", "medium")
        
        prompt_parts = [
            f"Creative Request: {message}\n"
        ]
        
        # Add creative context
        prompt_parts.append(f"Creative Approach: {approach}")
        prompt_parts.append(f"Domain: {domain}")
        prompt_parts.append(f"Creativity Level: {creativity_level}\n")
        
        if context:
            prompt_parts.append(f"Additional Context: {json.dumps(context, indent=2)}\n")
        
        # Add approach-specific instructions
        approach_instructions = {
            "storytelling": "Create engaging narratives with compelling characters, vivid descriptions, and strong plot development.",
            "brainstorming": "Generate diverse, innovative ideas using creative thinking techniques. Think outside the box and explore unconventional possibilities.",
            "content_creation": "Develop engaging, well-structured content that resonates with the target audience and achieves the intended purpose.",
            "problem_solving": "Apply creative problem-solving methods to find innovative and practical solutions.",
            "design_thinking": "Use design thinking principles to create user-centered, aesthetically pleasing solutions.",
            "general_creative": "Apply creative thinking and imagination to provide innovative, inspiring responses."
        }
        
        instruction = approach_instructions.get(approach, approach_instructions["general_creative"])
        prompt_parts.append(f"Creative Direction: {instruction}")
        
        # Add creativity level guidance
        creativity_guidance = {
            "low": "Focus on practical, straightforward creative solutions with proven effectiveness.",
            "medium": "Balance creativity with practicality, exploring interesting ideas while maintaining feasibility.",
            "high": "Push creative boundaries, explore unconventional ideas, and think innovatively.",
            "experimental": "Be bold and experimental, challenge conventions, and explore radical new possibilities."
        }
        
        guidance = creativity_guidance.get(creativity_level, creativity_guidance["medium"])
        prompt_parts.append(f"Creativity Guidance: {guidance}")
        
        prompt_parts.append(
            "\nEnsure your creative response includes:\n"
            "- Original, imaginative content\n"
            "- Engaging and inspiring language\n"
            "- Clear structure and flow\n"
            "- Relevant examples or details\n"
            "- Creative flair that matches the request"
        )
        
        return "\n".join(prompt_parts)
    
    def _format_creative_response(self, response: str, approach: str) -> str:
        """Format the creative response for better presentation"""
        
        # Add creative formatting based on approach
        if approach == "storytelling":
            # Add story formatting
            response = self._format_story(response)
        elif approach == "brainstorming":
            # Add idea list formatting
            response = self._format_ideas(response)
        elif approach == "content_creation":
            # Add content structure
            response = self._format_content(response)
        
        return response
    
    def _format_story(self, content: str) -> str:
        """Format story content"""
        # Simple story formatting - in a real system this could be more sophisticated
        if not content.startswith("# ") and not content.startswith("**"):
            # Add a story header if not present
            lines = content.split('\n')
            if len(lines) > 0 and not lines[0].strip().startswith(('**', '#', 'Title:')):
                content = "**Story**\n\n" + content
        
        return content
    
    def _format_ideas(self, content: str) -> str:
        """Format brainstorming ideas"""
        # Ensure ideas are properly formatted as a list
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')):
                if any(word in line.lower() for word in ['idea', 'concept', 'suggestion']):
                    line = f"• {line}"
            formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def _format_content(self, content: str) -> str:
        """Format content creation output"""
        # Basic content formatting
        return content
    
    async def brainstorm_session(self, topic: str, technique: str = "mind_mapping", 
                                num_ideas: int = 10) -> AgentResponse:
        """Specialized brainstorming session"""
        
        if technique not in self.techniques:
            technique = "mind_mapping"
        
        brainstorm_prompt = f"""
        Conduct a {technique} brainstorming session for the topic: "{topic}"
        
        Generate {num_ideas} creative, diverse, and innovative ideas.
        
        Use the {technique} technique:
        - If mind_mapping: Create a central concept with branching ideas
        - If free_writing: Generate a continuous flow of related ideas
        - If word_association: Build ideas through word connections
        - If lateral_thinking: Approach from unexpected angles
        - If reverse_brainstorming: Consider opposite or inverse approaches
        
        Present the ideas in a clear, organized format with brief explanations.
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": brainstorm_prompt}])
            
            return AgentResponse(
                content=response,
                agent_name=self.name,
                tools_used=["brainstorming", technique],
                confidence=0.9,
                reasoning=f"Brainstorming session using {technique} technique",
                metadata={
                    "brainstorm_technique": technique,
                    "topic": topic,
                    "requested_ideas": num_ideas
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"Unable to complete brainstorming session due to error: {e}",
                agent_name=self.name,
                confidence=0.1,
                metadata={"error": str(e)}
            )
    
    async def story_generator(self, genre: str, characters: List[str], 
                            setting: str, length: str = "short") -> AgentResponse:
        """Generate a story with specified parameters"""
        
        story_prompt = f"""
        Create a {length} {genre} story with the following elements:
        
        Characters: {', '.join(characters)}
        Setting: {setting}
        
        Include:
        - Compelling plot development
        - Character development and dialogue
        - Vivid descriptions of the setting
        - A satisfying resolution
        - Appropriate tone for the {genre} genre
        
        Length guidelines:
        - Short: 300-500 words
        - Medium: 800-1200 words  
        - Long: 1500+ words
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": story_prompt}])
            
            formatted_story = self._format_story(response)
            
            return AgentResponse(
                content=formatted_story,
                agent_name=self.name,
                tools_used=["story_generation"],
                confidence=0.95,
                reasoning="Custom story generated with specified parameters",
                metadata={
                    "genre": genre,
                    "characters": characters,
                    "setting": setting,
                    "length": length
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"Unable to generate story due to error: {e}",
                agent_name=self.name,
                confidence=0.1,
                metadata={"error": str(e)}
            )
    
    async def creative_writing_prompt(self, prompt_type: str = "random") -> AgentResponse:
        """Generate creative writing prompts"""
        
        prompt_types = {
            "character": "Create a writing prompt focused on character development",
            "setting": "Create a writing prompt centered around an interesting setting", 
            "conflict": "Create a writing prompt that introduces a compelling conflict",
            "mystery": "Create a mysterious writing prompt that hooks the reader",
            "sci-fi": "Create a science fiction writing prompt with futuristic elements",
            "fantasy": "Create a fantasy writing prompt with magical elements",
            "random": "Create an unexpected, unique writing prompt that combines different elements"
        }
        
        prompt_instruction = prompt_types.get(prompt_type, prompt_types["random"])
        
        writing_prompt_request = f"""
        {prompt_instruction}
        
        The prompt should be:
        - Intriguing and thought-provoking
        - Specific enough to spark ideas but open enough for interpretation
        - Include interesting details or constraints
        - Be suitable for various skill levels
        
        Provide 3 different prompts of this type.
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": writing_prompt_request}])
            
            return AgentResponse(
                content=response,
                agent_name=self.name,
                tools_used=["prompt_generation"],
                confidence=0.9,
                reasoning=f"Creative writing prompts generated for {prompt_type} type",
                metadata={
                    "prompt_type": prompt_type,
                    "prompt_count": 3
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"Unable to generate writing prompts due to error: {e}",
                agent_name=self.name,
                confidence=0.1,
                metadata={"error": str(e)}
            )

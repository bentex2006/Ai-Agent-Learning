import asyncio
import json
import re
from typing import Dict, Any, List, Optional

from .base import BaseAgent, AgentResponse
from config import settings


class CodeAgent(BaseAgent):

    def __init__(self):
        config = settings.get_agent_config("code")
        super().__init__(config)
        
        # Supported programming languages
        self.supported_languages = [
            "python", "javascript", "typescript", "java", "c", "cpp", "c++",
            "go", "rust", "html", "css", "sql", "bash", "shell", "json", "yaml"
        ]
    
    async def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """Process code-related queries"""
        
        # Analyze the coding intent
        intent_analysis = await self._analyze_coding_intent(message)
        
        # Determine the type of coding task
        task_type = intent_analysis.get("task_type", "general")
        
        tools_used = []
        execution_result = ""
        
        # Handle different types of coding tasks
        if task_type == "execution" and "code_exec" in self.get_available_tools():
            execution_result = await self._execute_code_safely(message)
            tools_used.append("code_exec")
        elif task_type == "file_operation" and "file_ops" in self.get_available_tools():
            file_result = await self._handle_file_operations(message)
            tools_used.append("file_ops")
        
        # Build the coding prompt
        coding_prompt = self._build_coding_prompt(message, intent_analysis, execution_result, context)
        
        # Get conversation history for context
        conversation_history = self.conversation_context.get_recent_messages(3)
        
        # Build messages for LLM
        messages = []
        
        # Add conversation history
        for hist in conversation_history:
            messages.append({"role": "user", "content": hist["user"]})
            messages.append({"role": "assistant", "content": hist["assistant"]})
        
        # Add current query
        messages.append({"role": "user", "content": coding_prompt})
        
        try:
            response_content = await self._call_llm(messages)
            
            # Post-process the response for code formatting
            formatted_response = self._format_code_response(response_content)
            
            # Add to conversation context
            self.add_to_context(message, formatted_response)
            
            return AgentResponse(
                content=formatted_response,
                agent_name=self.name,
                tools_used=tools_used,
                confidence=0.9,
                reasoning=f"Code task processed: {task_type}",
                metadata={
                    "task_type": task_type,
                    "intent_analysis": intent_analysis,
                    "languages_detected": intent_analysis.get("languages", []),
                    "execution_performed": bool(execution_result)
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"I encountered an error while processing your code request: {e}",
                agent_name=self.name,
                tools_used=tools_used,
                confidence=0.1,
                reasoning="Error occurred during code processing",
                metadata={"error": str(e)}
            )
    
    def can_handle(self, message: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Determine if this agent can handle the coding query"""
        base_score = super().can_handle(message, context)
        
        message_lower = message.lower()
        
        # Code-related keywords
        code_keywords = [
            "code", "program", "script", "function", "class", "method", "algorithm",
            "debug", "error", "bug", "fix", "optimize", "refactor", "review",
            "implement", "create", "write", "develop", "build", "test"
        ]
        
        # Programming language keywords
        lang_keywords = self.supported_languages + ["programming", "software", "development"]
        
        # Code-specific patterns
        code_patterns = [
            r"```", r"def\s+\w+", r"function\s+\w+", r"class\s+\w+", r"import\s+\w+",
            r"#include", r"public\s+class", r"console\.log", r"print\("
        ]
        
        keyword_score = 0
        
        # Check for code keywords
        for keyword in code_keywords:
            if keyword in message_lower:
                keyword_score += 0.25
        
        # Check for language keywords
        for lang in lang_keywords:
            if lang in message_lower:
                keyword_score += 0.3
        
        # Check for code patterns
        for pattern in code_patterns:
            if re.search(pattern, message):
                keyword_score += 0.4
                break
        
        # Boost for explicit code requests
        if any(phrase in message_lower for phrase in ["write code", "create function", "debug this", "fix the code"]):
            keyword_score += 0.5
        
        return min(base_score + keyword_score, 1.0)
    
    async def _analyze_coding_intent(self, message: str) -> Dict[str, Any]:
        """Analyze the coding intent of the user message"""
        
        intent_prompt = f"""
        Analyze this coding-related message and determine:
        1. Task type (generation, debugging, review, explanation, execution, optimization, file_operation)
        2. Programming languages mentioned or implied
        3. Specific requirements or constraints
        4. Complexity level (1-5)
        5. Whether code execution might be needed
        
        Message: "{message}"
        
        Respond in JSON format.
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": intent_prompt}])
            
            # Try to parse JSON response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                
                # Validate and set defaults
                analysis.setdefault("task_type", "generation")
                analysis.setdefault("languages", [])
                analysis.setdefault("complexity", 3)
                analysis.setdefault("needs_execution", False)
                
                return analysis
            
        except Exception as e:
            pass
        
        # Fallback analysis
        return {
            "task_type": self._detect_task_type(message),
            "languages": self._detect_languages(message),
            "complexity": 3,
            "needs_execution": "run" in message.lower() or "execute" in message.lower()
        }
    
    def _detect_task_type(self, message: str) -> str:
        """Detect the type of coding task"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["debug", "fix", "error", "bug", "issue"]):
            return "debugging"
        elif any(word in message_lower for word in ["review", "check", "analyze", "improve"]):
            return "review"
        elif any(word in message_lower for word in ["explain", "understand", "how", "what does"]):
            return "explanation"
        elif any(word in message_lower for word in ["run", "execute", "test"]):
            return "execution"
        elif any(word in message_lower for word in ["optimize", "performance", "faster", "efficient"]):
            return "optimization"
        elif any(word in message_lower for word in ["file", "save", "load", "read", "write"]):
            return "file_operation"
        else:
            return "generation"
    
    def _detect_languages(self, message: str) -> List[str]:
        """Detect programming languages mentioned in the message"""
        detected = []
        message_lower = message.lower()
        
        for lang in self.supported_languages:
            if lang in message_lower:
                detected.append(lang)
        
        # Special cases
        if "js" in message_lower and "javascript" not in detected:
            detected.append("javascript")
        if "py" in message_lower and "python" not in detected:
            detected.append("python")
        
        return detected
    
    async def _execute_code_safely(self, message: str) -> str:
        """Execute code safely using the code execution tool"""
        try:
            # Extract code from message
            code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', message, re.DOTALL)
            
            if not code_blocks:
                # Try to find inline code
                inline_code = re.findall(r'`([^`]+)`', message)
                if inline_code:
                    code_blocks = inline_code
            
            if code_blocks:
                # Execute the first code block found
                code = code_blocks[0].strip()
                result = await self.use_tool("code_exec", code=code, language="python")
                
                if "error" in result:
                    return f"Execution error: {result['error']}"
                else:
                    return f"Execution result:\n{result.get('output', 'No output')}"
            
            return "No executable code found in the message."
            
        except Exception as e:
            return f"Code execution error: {e}"
    
    async def _handle_file_operations(self, message: str) -> str:
        """Handle file operations using the file ops tool"""
        try:
            # This is a simplified implementation
            # In a real system, you'd parse the message more carefully
            if "save" in message.lower() or "write" in message.lower():
                return "File operation: save/write"
            elif "load" in message.lower() or "read" in message.lower():
                return "File operation: load/read"
            else:
                return "File operation: general"
                
        except Exception as e:
            return f"File operation error: {e}"
    
    def _build_coding_prompt(self, message: str, intent_analysis: Dict[str, Any], 
                           execution_result: str, context: Optional[Dict[str, Any]]) -> str:
        """Build the coding prompt for the LLM"""
        
        prompt_parts = [
            f"Coding Request: {message}\n"
        ]
        
        # Add intent analysis context
        task_type = intent_analysis.get("task_type", "general")
        languages = intent_analysis.get("languages", [])
        
        if languages:
            prompt_parts.append(f"Languages involved: {', '.join(languages)}\n")
        
        if execution_result:
            prompt_parts.append(f"Execution Results:\n{execution_result}\n")
        
        if context:
            prompt_parts.append(f"Additional Context: {json.dumps(context, indent=2)}\n")
        
        # Add task-specific instructions
        task_instructions = {
            "generation": "Please provide clean, well-documented code with explanations.",
            "debugging": "Please identify the issue and provide a corrected version with explanation.",
            "review": "Please review the code and provide feedback on improvements, best practices, and potential issues.",
            "explanation": "Please explain how the code works, breaking down key concepts and logic.",
            "execution": "Please analyze the execution results and provide insights or next steps.",
            "optimization": "Please suggest optimizations for better performance and efficiency.",
            "file_operation": "Please help with the file operation, ensuring safe and proper handling."
        }
        
        instruction = task_instructions.get(task_type, "Please provide a helpful response to this coding request.")
        prompt_parts.append(f"\n{instruction}")
        
        prompt_parts.append(
            "\nEnsure your response includes:\n"
            "- Clear, readable code (if applicable)\n"
            "- Proper explanations and comments\n"
            "- Best practices and considerations\n"
            "- Any potential issues or limitations"
        )
        
        return "\n".join(prompt_parts)
    
    def _format_code_response(self, response: str) -> str:
        """Format the code response for better readability"""
        # This is a simple formatter - in a real system you might use more sophisticated formatting
        
        # Ensure code blocks are properly formatted
        response = re.sub(r'```(\w+)?\s*\n', r'```\1\n', response)
        
        # Add language hints where missing
        response = re.sub(r'```\n(def |class |import |from )', r'```python\n\1', response)
        response = re.sub(r'```\n(function |const |let |var )', r'```javascript\n\1', response)
        response = re.sub(r'```\n(SELECT |INSERT |UPDATE |DELETE )', r'```sql\n\1', response)
        
        return response
    
    async def code_review(self, code: str, language: str = "python") -> AgentResponse:
        """Specialized method for code review"""
        
        review_prompt = f"""
        Please perform a comprehensive code review of the following {language} code:
        
        ```{language}
        {code}
        ```
        
        Please provide:
        1. Overall assessment of code quality
        2. Potential bugs or issues
        3. Performance improvements
        4. Best practices recommendations
        5. Security considerations (if applicable)
        """
        
        try:
            response = await self._call_llm([
                {"role": "user", "content": review_prompt}
            ])
            
            return AgentResponse(
                content=self._format_code_response(response),
                agent_name=self.name,
                tools_used=[],
                confidence=0.9,
                reasoning="Provided comprehensive code review with detailed analysis"
            )
        except Exception as e:
            return AgentResponse(
                content=f"Error during code review: {str(e)}",
                agent_name=self.name,
                tools_used=[],
                confidence=0.0,
                reasoning="Code review failed due to error"
            )
        
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from .base import BaseAgent, AgentResponse
from config import settings


class TaskAgent(BaseAgent):

    def __init__(self):
        config = settings.get_agent_config("task")
        super().__init__(config)
        
        # Task management domains
        self.task_domains = [
            "project_management", "planning", "scheduling", "coordination",
            "workflow_optimization", "resource_allocation", "milestone_tracking",
            "goal_setting", "priority_management", "delegation"
        ]
        
        # Project methodologies
        self.methodologies = [
            "agile", "scrum", "kanban", "waterfall", "lean", "gtd",
            "pomodoro", "eisenhower_matrix", "okr", "smart_goals"
        ]
    
    async def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> AgentResponse:
        """Process task and project management requests"""
        
        # Analyze task management intent
        task_analysis = await self._analyze_task_intent(message)
        
        # Determine task type and approach
        task_type = task_analysis.get("task_type", "general_planning")
        methodology = task_analysis.get("methodology", "agile")
        
        tools_used = []
        
        # Handle file operations for saving plans, schedules, etc.
        if task_analysis.get("needs_file_save", False) and "file_ops" in self.get_available_tools():
            tools_used.append("file_ops")
        
        # Build task management prompt
        task_prompt = self._build_task_prompt(message, task_analysis, context)
        
        # Get conversation history for project context
        conversation_history = self.conversation_context.get_recent_messages(3)
        
        # Build messages for LLM
        messages = []
        
        # Add conversation history for project continuity
        for hist in conversation_history:
            messages.append({"role": "user", "content": hist["user"]})
            messages.append({"role": "assistant", "content": hist["assistant"]})
        
        # Add current task request
        messages.append({"role": "user", "content": task_prompt})
        
        try:
            response_content = await self._call_llm(messages)
            
            # Format response for task management
            formatted_response = self._format_task_response(response_content, task_type)
            
            # Add to conversation context
            self.add_to_context(message, formatted_response)
            
            return AgentResponse(
                content=formatted_response,
                agent_name=self.name,
                tools_used=tools_used,
                confidence=0.9,
                reasoning=f"Task management processed using {methodology} approach for {task_type}",
                metadata={
                    "task_type": task_type,
                    "methodology": methodology,
                    "analysis": task_analysis,
                    "complexity": task_analysis.get("complexity", "medium")
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"I encountered an issue while processing your task management request: {e}",
                agent_name=self.name,
                tools_used=tools_used,
                confidence=0.1,
                reasoning="Error occurred during task processing",
                metadata={"error": str(e)}
            )
    
    def can_handle(self, message: str, context: Optional[Dict[str, Any]] = None) -> float:
        """Determine if this agent can handle the task management request"""
        base_score = super().can_handle(message, context)
        
        message_lower = message.lower()
        
        # Task management keywords
        task_keywords = [
            "plan", "planning", "project", "task", "schedule", "organize",
            "manage", "coordinate", "timeline", "deadline", "milestone",
            "goal", "objective", "strategy", "workflow", "process"
        ]
        
        # Action words for task management
        action_words = [
            "create plan", "make schedule", "organize", "break down",
            "prioritize", "track progress", "set goals", "manage time",
            "coordinate", "delegate", "optimize", "streamline"
        ]
        
        # Project-related terms
        project_terms = [
            "project management", "agile", "scrum", "kanban", "sprint",
            "backlog", "roadmap", "deliverables", "resources", "budget"
        ]
        
        keyword_score = 0
        
        # Check for task keywords
        for keyword in task_keywords:
            if keyword in message_lower:
                keyword_score += 0.2
        
        # Check for action words
        for action in action_words:
            if action in message_lower:
                keyword_score += 0.3
        
        # Check for project terms
        for term in project_terms:
            if term in message_lower:
                keyword_score += 0.4
        
        # Boost for explicit task requests
        task_phrases = [
            "help me plan", "create a plan", "organize this", "break this down",
            "manage this project", "set up a timeline", "track progress"
        ]
        
        if any(phrase in message_lower for phrase in task_phrases):
            keyword_score += 0.5
        
        return min(base_score + keyword_score, 1.0)
    
    async def _analyze_task_intent(self, message: str) -> Dict[str, Any]:
        """Analyze the task management intent of the user message"""
        
        intent_prompt = f"""
        Analyze this task management request and determine:
        1. Task type (planning, scheduling, coordination, tracking, optimization, delegation)
        2. Project scale (personal, team, organization)
        3. Timeline scope (daily, weekly, monthly, quarterly, annual)
        4. Methodology preference (agile, scrum, kanban, traditional, gtd)
        5. Complexity level (1-5)
        6. Whether file saving might be needed for plans/schedules
        
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
                analysis.setdefault("task_type", "planning")
                analysis.setdefault("scale", "personal")
                analysis.setdefault("timeline", "weekly")
                analysis.setdefault("methodology", "agile")
                analysis.setdefault("complexity", 3)
                analysis.setdefault("needs_file_save", False)
                
                return analysis
            
        except Exception as e:
            pass
        
        # Fallback analysis
        return {
            "task_type": self._detect_task_type(message),
            "scale": self._detect_project_scale(message),
            "timeline": "weekly",
            "methodology": "agile",
            "complexity": 3,
            "needs_file_save": "save" in message.lower() or "file" in message.lower()
        }
    
    def _detect_task_type(self, message: str) -> str:
        """Detect the type of task management needed"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["schedule", "timeline", "calendar", "when"]):
            return "scheduling"
        elif any(word in message_lower for word in ["coordinate", "team", "collaborate", "delegate"]):
            return "coordination"
        elif any(word in message_lower for word in ["track", "progress", "status", "update"]):
            return "tracking"
        elif any(word in message_lower for word in ["optimize", "improve", "efficient", "streamline"]):
            return "optimization"
        elif any(word in message_lower for word in ["assign", "delegate", "distribute", "allocate"]):
            return "delegation"
        else:
            return "planning"
    
    def _detect_project_scale(self, message: str) -> str:
        """Detect the scale of the project"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["my", "personal", "individual", "myself"]):
            return "personal"
        elif any(word in message_lower for word in ["team", "group", "colleague", "department"]):
            return "team"
        elif any(word in message_lower for word in ["company", "organization", "enterprise", "business"]):
            return "organization"
        else:
            return "personal"
    
    def _build_task_prompt(self, message: str, task_analysis: Dict[str, Any], 
                          context: Optional[Dict[str, Any]]) -> str:
        """Build the task management prompt for the LLM"""
        
        task_type = task_analysis.get("task_type", "planning")
        scale = task_analysis.get("scale", "personal")
        timeline = task_analysis.get("timeline", "weekly")
        methodology = task_analysis.get("methodology", "agile")
        complexity = task_analysis.get("complexity", 3)
        
        prompt_parts = [
            f"Task Management Request: {message}\n"
        ]
        
        # Add task context
        prompt_parts.append(f"Task Type: {task_type}")
        prompt_parts.append(f"Project Scale: {scale}")
        prompt_parts.append(f"Timeline Scope: {timeline}")
        prompt_parts.append(f"Methodology: {methodology}")
        prompt_parts.append(f"Complexity Level: {complexity}/5\n")
        
        if context:
            prompt_parts.append(f"Additional Context: {json.dumps(context, indent=2)}\n")
        
        # Add task-specific instructions
        task_instructions = {
            "planning": "Create a comprehensive plan with clear objectives, tasks, timelines, and dependencies.",
            "scheduling": "Develop a detailed schedule with time allocations, deadlines, and milestones.",
            "coordination": "Design coordination strategies for team collaboration and communication.",
            "tracking": "Establish tracking mechanisms for progress monitoring and status updates.",
            "optimization": "Analyze current processes and suggest improvements for efficiency and effectiveness.",
            "delegation": "Create delegation plans with clear responsibilities and accountability measures."
        }
        
        instruction = task_instructions.get(task_type, task_instructions["planning"])
        prompt_parts.append(f"Primary Focus: {instruction}")
        
        # Add methodology-specific guidance
        methodology_guidance = {
            "agile": "Use iterative approach with sprints, user stories, and continuous improvement.",
            "scrum": "Apply Scrum framework with defined roles, ceremonies, and artifacts.",
            "kanban": "Implement visual workflow management with continuous delivery focus.",
            "waterfall": "Use sequential phases with clear gates and documentation.",
            "gtd": "Apply Getting Things Done principles for personal productivity.",
            "lean": "Focus on waste elimination and value stream optimization."
        }
        
        guidance = methodology_guidance.get(methodology, "Use best practices for project management.")
        prompt_parts.append(f"Methodology Guidance: {guidance}")
        
        prompt_parts.append(
            f"\nEnsure your {task_type} response includes:\n"
            "- Clear, actionable steps\n"
            "- Realistic timelines and milestones\n"
            "- Resource requirements and constraints\n"
            "- Risk considerations and mitigation strategies\n"
            "- Success criteria and measurement methods\n"
            "- Next steps and follow-up actions"
        )
        
        return "\n".join(prompt_parts)
    
    def _format_task_response(self, response: str, task_type: str) -> str:
        """Format the task management response for better presentation"""
        
        # Add task-specific formatting
        if task_type == "planning":
            response = self._format_plan(response)
        elif task_type == "scheduling":
            response = self._format_schedule(response)
        elif task_type == "coordination":
            response = self._format_coordination(response)
        
        return response
    
    def _format_plan(self, content: str) -> str:
        """Format planning content"""
        # Ensure plan has proper structure
        if not any(header in content for header in ["## ", "### ", "**Objective", "**Goals"]):
            content = f"## Project Plan\n\n{content}"
        
        return content
    
    def _format_schedule(self, content: str) -> str:
        """Format schedule content"""
        # Ensure schedule has timeline structure
        return content
    
    def _format_coordination(self, content: str) -> str:
        """Format coordination content"""
        # Ensure coordination plan has clear structure
        return content
    
    async def create_project_plan(self, project_name: str, objectives: List[str], 
                                deadline: str, resources: List[str]) -> AgentResponse:
        """Create a comprehensive project plan"""
        
        plan_prompt = f"""
        Create a comprehensive project plan for: "{project_name}"
        
        Project Details:
        - Objectives: {', '.join(objectives)}
        - Deadline: {deadline}
        - Available Resources: {', '.join(resources)}
        
        Include:
        1. Project scope and deliverables
        2. Work breakdown structure (WBS)
        3. Timeline and milestones
        4. Resource allocation
        5. Risk assessment and mitigation
        6. Success criteria and metrics
        7. Communication plan
        8. Quality assurance approach
        
        Format as a professional project plan document.
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": plan_prompt}])
            
            formatted_plan = self._format_plan(response)
            
            return AgentResponse(
                content=formatted_plan,
                agent_name=self.name,
                tools_used=["project_planning"],
                confidence=0.95,
                reasoning="Comprehensive project plan created with all key components",
                metadata={
                    "project_name": project_name,
                    "objectives_count": len(objectives),
                    "deadline": deadline,
                    "resources_count": len(resources)
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"Unable to create project plan due to error: {e}",
                agent_name=self.name,
                confidence=0.1,
                metadata={"error": str(e)}
            )
    
    async def break_down_task(self, main_task: str, complexity: str = "medium") -> AgentResponse:
        """Break down a complex task into manageable subtasks"""
        
        breakdown_prompt = f"""
        Break down this complex task into manageable subtasks: "{main_task}"
        
        Complexity Level: {complexity}
        
        For each subtask, provide:
        1. Clear, actionable description
        2. Estimated time/effort required
        3. Dependencies on other subtasks
        4. Required skills or resources
        5. Success criteria
        
        Organize subtasks in logical order and consider:
        - Parallelizable vs sequential tasks
        - Critical path dependencies
        - Resource constraints
        - Risk factors
        
        Present as a structured task breakdown with priority levels.
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": breakdown_prompt}])
            
            return AgentResponse(
                content=response,
                agent_name=self.name,
                tools_used=["task_breakdown"],
                confidence=0.9,
                reasoning="Task broken down into manageable subtasks with dependencies",
                metadata={
                    "main_task": main_task,
                    "complexity": complexity
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"Unable to break down task due to error: {e}",
                agent_name=self.name,
                confidence=0.1,
                metadata={"error": str(e)}
            )
    
    async def prioritize_tasks(self, tasks: List[str], criteria: str = "eisenhower") -> AgentResponse:
        """Prioritize a list of tasks using specified criteria"""
        
        prioritization_methods = {
            "eisenhower": "Use the Eisenhower Matrix (Urgent/Important quadrants)",
            "moscow": "Use MoSCoW method (Must have, Should have, Could have, Won't have)",
            "rice": "Use RICE scoring (Reach, Impact, Confidence, Effort)",
            "value": "Prioritize by business/personal value and impact",
            "effort": "Prioritize by effort required (quick wins first)"
        }
        
        method_description = prioritization_methods.get(criteria, prioritization_methods["eisenhower"])
        
        priority_prompt = f"""
        Prioritize the following tasks using {method_description}:
        
        Tasks:
        {chr(10).join([f"- {task}" for task in tasks])}
        
        For each task, provide:
        1. Priority level/category
        2. Reasoning for the priority assignment
        3. Recommended order of execution
        4. Estimated effort/time required
        
        Present results in a clear priority matrix or ranked list.
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": priority_prompt}])
            
            return AgentResponse(
                content=response,
                agent_name=self.name,
                tools_used=["task_prioritization", criteria],
                confidence=0.9,
                reasoning=f"Tasks prioritized using {criteria} method",
                metadata={
                    "task_count": len(tasks),
                    "prioritization_method": criteria
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"Unable to prioritize tasks due to error: {e}",
                agent_name=self.name,
                confidence=0.1,
                metadata={"error": str(e)}
            )
    
    async def create_timeline(self, project_name: str, tasks: List[Dict[str, Any]], 
                            start_date: str) -> AgentResponse:
        """Create a project timeline with Gantt-like structure"""
        
        timeline_prompt = f"""
        Create a detailed project timeline for "{project_name}" starting {start_date}:
        
        Tasks:
        {json.dumps(tasks, indent=2)}
        
        Create a timeline that includes:
        1. Task scheduling with start and end dates
        2. Dependencies between tasks
        3. Critical path identification
        4. Milestone markers
        5. Resource allocation timeline
        6. Buffer time for risk mitigation
        
        Present as a structured timeline with:
        - Weekly/monthly view
        - Task dependencies clearly marked
        - Critical milestones highlighted
        - Resource conflicts identified
        """
        
        try:
            response = await self._call_llm([{"role": "user", "content": timeline_prompt}])
            
            formatted_timeline = self._format_schedule(response)
            
            return AgentResponse(
                content=formatted_timeline,
                agent_name=self.name,
                tools_used=["timeline_creation"],
                confidence=0.9,
                reasoning="Project timeline created with dependencies and milestones",
                metadata={
                    "project_name": project_name,
                    "task_count": len(tasks),
                    "start_date": start_date
                }
            )
            
        except Exception as e:
            return AgentResponse(
                content=f"Unable to create timeline due to error: {e}",
                agent_name=self.name,
                confidence=0.1,
                metadata={"error": str(e)}
            )

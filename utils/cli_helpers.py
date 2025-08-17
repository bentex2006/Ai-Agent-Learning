import sys
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.tree import Tree
import re


# Initialize rich console
console = Console()


def display_banner():
    """Display the application banner"""
    
    banner_text = """
    ███╗   ███╗ ██████╗██████╗      █████╗ ██╗      █████╗  ██████╗ ███████╗███╗   ██╗████████╗
    ████╗ ████║██╔════╝██╔══██╗    ██╔══██╗██║     ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
    ██╔████╔██║██║     ██████╔╝    ███████║██║     ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
    ██║╚██╔╝██║██║     ██╔═══╝     ██╔══██║██║     ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
    ██║ ╚═╝ ██║╚██████╗██║         ██║  ██║██║     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
    ╚═╝     ╚═╝ ╚═════╝╚═╝         ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
    """
    
    console.print(Panel(
        Text(banner_text, style="bold blue") + 
        Text("\n\nMulti-Capability Platform AI Agent", style="bold cyan") +
        Text("\nIntelligent Multi-Agent System for Complex Tasks", style="dim"),
        border_style="blue",
        padding=(1, 2)
    ))


def display_agent_info(agent_name: str, agent_info: Dict[str, Any]):
    """Display information about an agent"""
    
    # Create agent info table
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Property", style="cyan", min_width=15)
    table.add_column("Value", style="white")
    
    # Add agent properties
    table.add_row("Name", agent_name.title())
    table.add_row("Personality", agent_info.get("personality", "Unknown"))
    
    # Format capabilities
    capabilities = agent_info.get("capabilities", [])
    if capabilities:
        capabilities_text = ", ".join(capabilities)
        table.add_row("Capabilities", capabilities_text)
    
    # Format tools
    tools = agent_info.get("tools", [])
    if tools:
        tools_text = ", ".join(tools)
        table.add_row("Tools", tools_text)
    
    # Add description if available
    description = agent_info.get("description", "")
    if description:
        # Truncate long descriptions
        if len(description) > 100:
            description = description[:97] + "..."
        table.add_row("Description", description)
    
    # Display in a panel
    console.print(Panel(
        table,
        title=f"[bold magenta]{agent_name.title()} Agent[/bold magenta]",
        border_style="magenta",
        padding=(1, 1)
    ))


def format_response(content: str, response_type: str = "general") -> str:
    """Format agent response content for better display"""
    
    try:
        # Handle markdown content
        if "```" in content or "#" in content or "*" in content:
            return Markdown(content)
        
        # Handle code blocks separately for syntax highlighting
        code_pattern = r'```(\w+)?\n(.*?)\n```'
        matches = re.findall(code_pattern, content, re.DOTALL)
        
        if matches:
            formatted_parts = []
            last_end = 0
            
            for match in re.finditer(code_pattern, content, re.DOTALL):
                # Add text before code block
                if match.start() > last_end:
                    text_part = content[last_end:match.start()].strip()
                    if text_part:
                        formatted_parts.append(text_part)
                
                # Add syntax-highlighted code block
                language = match.group(1) or "text"
                code = match.group(2)
                
                try:
                    syntax = Syntax(code, language, theme="monokai", line_numbers=True)
                    formatted_parts.append(syntax)
                except:
                    # Fallback to plain text if syntax highlighting fails
                    formatted_parts.append(f"```{language}\n{code}\n```")
                
                last_end = match.end()
            
            # Add remaining text
            if last_end < len(content):
                remaining_text = content[last_end:].strip()
                if remaining_text:
                    formatted_parts.append(remaining_text)
            
            # If we have multiple parts, return them separately
            if len(formatted_parts) > 1:
                for part in formatted_parts:
                    if isinstance(part, str):
                        console.print(part)
                    else:
                        console.print(part)
                return ""  # Already printed
        
        # Default: return as markdown
        return Markdown(content)
        
    except Exception:
        # Fallback to plain text if formatting fails
        return content


def display_progress(description: str = "Processing..."):
    """Create a progress spinner for long operations"""
    
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    )


def display_error(error_message: str, title: str = "Error"):
    """Display an error message in a formatted panel"""
    
    console.print(Panel(
        f"[red]{error_message}[/red]",
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        padding=(1, 2)
    ))


def display_warning(warning_message: str, title: str = "Warning"):
    """Display a warning message in a formatted panel"""
    
    console.print(Panel(
        f"[yellow]{warning_message}[/yellow]",
        title=f"[bold yellow]{title}[/bold yellow]",
        border_style="yellow",
        padding=(1, 2)
    ))


def display_success(success_message: str, title: str = "Success"):
    """Display a success message in a formatted panel"""
    
    console.print(Panel(
        f"[green]{success_message}[/green]",
        title=f"[bold green]{title}[/bold green]",
        border_style="green",
        padding=(1, 2)
    ))


def display_agent_comparison(agents_info: Dict[str, Dict[str, Any]]):
    """Display a comparison table of available agents"""
    
    table = Table(title="Available Agents Comparison")
    
    # Add columns
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Personality", style="magenta")
    table.add_column("Primary Capabilities", style="green")
    table.add_column("Tools", style="blue")
    
    # Add agent rows
    for agent_name, info in agents_info.items():
        capabilities = info.get("capabilities", [])
        tools = info.get("tools", [])
        
        # Format capabilities (show first 3)
        cap_display = ", ".join(capabilities[:3])
        if len(capabilities) > 3:
            cap_display += f" (+{len(capabilities)-3} more)"
        
        # Format tools
        tools_display = ", ".join(tools) if tools else "None"
        
        table.add_row(
            agent_name.title(),
            info.get("personality", "Unknown"),
            cap_display,
            tools_display
        )
    
    console.print(table)


def display_conversation_history(history: List[Dict[str, Any]], limit: int = 5):
    """Display conversation history in a formatted way"""
    
    if not history:
        console.print("[dim]No conversation history available[/dim]")
        return
    
    console.print(Panel(
        "[bold]Recent Conversation History[/bold]",
        border_style="blue"
    ))
    
    # Show recent messages
    recent_history = history[-limit:] if len(history) > limit else history
    
    for i, entry in enumerate(recent_history, 1):
        user_msg = entry.get("user", "")
        response = entry.get("response", "")
        agent_used = entry.get("agent_used", "unknown")
        timestamp = entry.get("timestamp", "")
        
        # Truncate long messages
        if len(user_msg) > 100:
            user_msg = user_msg[:97] + "..."
        if len(response) > 150:
            response = response[:147] + "..."
        
        console.print(f"\n[dim]{i}. {timestamp}[/dim]")
        console.print(f"[bold cyan]You:[/bold cyan] {user_msg}")
        console.print(f"[bold green]{agent_used.title()}:[/bold green] {response}")


def display_tool_usage_stats(tool_stats: Dict[str, int]):
    """Display tool usage statistics"""
    
    if not tool_stats:
        console.print("[dim]No tool usage data available[/dim]")
        return
    
    table = Table(title="Tool Usage Statistics")
    table.add_column("Tool", style="cyan")
    table.add_column("Usage Count", style="green", justify="right")
    table.add_column("Usage %", style="blue", justify="right")
    
    total_usage = sum(tool_stats.values())
    
    # Sort by usage count
    sorted_tools = sorted(tool_stats.items(), key=lambda x: x[1], reverse=True)
    
    for tool_name, count in sorted_tools:
        percentage = (count / total_usage * 100) if total_usage > 0 else 0
        table.add_row(
            tool_name,
            str(count),
            f"{percentage:.1f}%"
        )
    
    console.print(table)


def display_system_status(status: Dict[str, Any]):
    """Display system status information"""
    
    # Create status panels
    panels = []
    
    # Session info panel
    session_info = Table(show_header=False, box=None)
    session_info.add_column("Property", style="cyan")
    session_info.add_column("Value", style="white")
    
    session_info.add_row("Session ID", status.get("session_id", "Unknown")[:8] + "...")
    session_info.add_row("Total Messages", str(status.get("total_messages", 0)))
    session_info.add_row("Memory Usage", f"{status.get('memory_usage', 0)} entries")
    
    if status.get("last_activity"):
        session_info.add_row("Last Activity", status["last_activity"])
    
    panels.append(Panel(session_info, title="[bold]Session Info[/bold]", border_style="blue"))
    
    # Agents panel
    active_agents = status.get("active_agents", [])
    agents_list = "\n".join([f"• {agent.title()}" for agent in active_agents])
    panels.append(Panel(agents_list, title="[bold]Active Agents[/bold]", border_style="green"))
    
    # Agent usage stats panel
    agent_stats = status.get("agent_usage_stats", {})
    if agent_stats:
        stats_table = Table(show_header=False, box=None)
        stats_table.add_column("Agent", style="magenta")
        stats_table.add_column("Uses", style="green", justify="right")
        
        for agent, count in sorted(agent_stats.items(), key=lambda x: x[1], reverse=True):
            stats_table.add_row(agent.title(), str(count))
        
        panels.append(Panel(stats_table, title="[bold]Agent Usage[/bold]", border_style="magenta"))
    
    # Display panels in columns
    console.print(Columns(panels, equal=True, expand=True))


def prompt_for_confirmation(message: str, default: bool = False) -> bool:
    """Prompt user for yes/no confirmation"""
    
    default_text = "Y/n" if default else "y/N"
    response = console.input(f"[bold cyan]{message}[/bold cyan] [{default_text}]: ").strip().lower()
    
    if not response:
        return default
    
    return response in ['y', 'yes', 'true', '1']


def display_help():
    """Display help information"""
    
    help_content = """
# MCP AI Agent Help

## Available Commands

### Interactive Mode Commands
- `/help` - Show this help message
- `/agents` - List all available agents and their capabilities
- `/switch <agent>` - Switch to a specific agent
- `/history` - Show recent conversation history
- `/clear` - Clear conversation history
- `/status` - Show system status and statistics
- `/exit` - Exit the application

### CLI Commands
- `mcp-agent interactive` - Start interactive chat session
- `mcp-agent ask "<message>"` - Ask a single question
- `mcp-agent list-agents` - List available agents
- `mcp-agent --help` - Show CLI help

## Available Agents

### Research Agent
- **Purpose**: Information gathering, fact-checking, analysis
- **Best for**: Research questions, current events, data analysis
- **Tools**: Web search, file operations

### Code Agent  
- **Purpose**: Programming, debugging, code review
- **Best for**: Coding tasks, technical problems, software development
- **Tools**: Code execution, file operations

### Creative Agent
- **Purpose**: Content creation, brainstorming, ideation
- **Best for**: Writing, creative projects, marketing content
- **Tools**: File operations

### Task Agent
- **Purpose**: Project management, planning, coordination
- **Best for**: Planning projects, organizing tasks, workflow optimization
- **Tools**: File operations

## Tips for Best Results

1. **Be specific** - Clear, detailed requests get better responses
2. **Use the right agent** - Each agent is optimized for different types of tasks
3. **Provide context** - Reference previous conversations or specific requirements
4. **Ask follow-up questions** - Agents can build on previous responses
5. **Use tools** - Agents can search the web, execute code, and manage files

## Examples

**Ask the research agent about a topic:**
- "What are the latest developments in AI?" 
- "Research the benefits of renewable energy"

**Get help from the code agent:**
- "Write a Python function to sort a list"
- "Debug this JavaScript error"

**Brainstorm with the creative agent:**
- "Help me write a blog post about productivity"
- "Generate ideas for a marketing campaign"

**Plan with the task agent:**
- "Help me organize a project timeline"
- "Break down this complex task into steps"
"""
    
    console.print(Markdown(help_content))

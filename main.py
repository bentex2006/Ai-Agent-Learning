import asyncio
import sys
import os
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner
from rich.markdown import Markdown

from config import Settings
from orchestration.coordinator import AgentCoordinator
from utils.logger import setup_logger
from utils.cli_helpers import display_banner, display_agent_info, format_response

# Initialize console and logger
console = Console()
logger = setup_logger()


@click.group()
@click.option('--config', '-c', help='Path to configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """MCP AI Agent - Multi-Capability Platform AI Agent System"""
    ctx.ensure_object(dict)
    
    # Load configuration
    settings = Settings()
    if config:
        settings = Settings(_env_file=config)
    
    # Setup logging level
    if verbose:
        logger.setLevel("DEBUG")
    
    ctx.obj['settings'] = settings
    ctx.obj['coordinator'] = AgentCoordinator(settings)


@cli.command()
@click.pass_context
def interactive(ctx):
    """Start interactive multi-agent chat session"""
    settings = ctx.obj['settings']
    coordinator = ctx.obj['coordinator']
    
    display_banner()
    
    console.print(Panel(
        "[bold green]Welcome to MCP AI Agent System![/bold green]\n\n"
        "Available commands:\n"
        "• [cyan]/help[/cyan] - Show this help\n"
        "• [cyan]/agents[/cyan] - List available agents\n"
        "• [cyan]/switch <agent>[/cyan] - Switch to specific agent\n"
        "• [cyan]/history[/cyan] - Show conversation history\n"
        "• [cyan]/clear[/cyan] - Clear conversation history\n"
        "• [cyan]/exit[/cyan] - Exit the system\n\n"
        "Just type your message to start chatting!",
        title="Instructions",
        border_style="blue"
    ))
    
    # Start interactive loop
    asyncio.run(interactive_loop(coordinator))


async def interactive_loop(coordinator: AgentCoordinator):
    """Main interactive chat loop"""
    current_agent = None
    
    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()
            
            if not user_input:
                continue
                
            # Handle commands
            if user_input.startswith('/'):
                if await handle_command(user_input, coordinator, current_agent):
                    break
                continue
            
            # Process message with coordinator
            with Live(Spinner("dots", text="Thinking..."), refresh_per_second=10):
                response = await coordinator.process_message(user_input, current_agent)
            
            # Display response
            if response.agent_used:
                console.print(f"\n[bold magenta]{response.agent_used.title()} Agent[/bold magenta]:")
                current_agent = response.agent_used
                
            # Format and display the response
            formatted_response = format_response(response.content)
            console.print(Panel(
                formatted_response,
                border_style="green",
                padding=(1, 2)
            ))
            
            # Show any tool usage
            if response.tools_used:
                console.print(f"\n[dim]Tools used: {', '.join(response.tools_used)}[/dim]")
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
            break
        except Exception as e:
            logger.error(f"Error in interactive loop: {e}")
            console.print(f"[red]Error: {e}[/red]")


async def handle_command(command: str, coordinator: AgentCoordinator, current_agent: Optional[str]) -> bool:
    """Handle CLI commands. Returns True if should exit."""
    cmd_parts = command[1:].split()
    cmd = cmd_parts[0].lower() if cmd_parts else ""
    
    if cmd == "help":
        console.print(Panel(
            "[bold]Available Commands:[/bold]\n\n"
            "• [cyan]/agents[/cyan] - List all available agents\n"
            "• [cyan]/switch <agent>[/cyan] - Switch to specific agent (research, code, creative, task)\n"
            "• [cyan]/history[/cyan] - Show conversation history\n"
            "• [cyan]/clear[/cyan] - Clear conversation history\n"
            "• [cyan]/status[/cyan] - Show system status\n"
            "• [cyan]/exit[/cyan] - Exit the system",
            title="Help",
            border_style="blue"
        ))
        
    elif cmd == "agents":
        agents_info = coordinator.get_available_agents()
        for agent_name, agent_info in agents_info.items():
            display_agent_info(agent_name, agent_info)
            
    elif cmd == "switch":
        if len(cmd_parts) < 2:
            console.print("[red]Usage: /switch <agent_name>[/red]")
        else:
            agent_name = cmd_parts[1].lower()
            if coordinator.has_agent(agent_name):
                console.print(f"[green]Switched to {agent_name.title()} Agent[/green]")
                return False
            else:
                console.print(f"[red]Unknown agent: {agent_name}[/red]")
                
    elif cmd == "history":
        history = coordinator.get_conversation_history()
        if history:
            console.print(Panel(
                "\n".join([f"[cyan]User:[/cyan] {h['user']}\n[green]Agent:[/green] {h['response'][:100]}..." 
                          for h in history[-5:]]),
                title="Recent History",
                border_style="blue"
            ))
        else:
            console.print("[yellow]No conversation history[/yellow]")
            
    elif cmd == "clear":
        coordinator.clear_history()
        console.print("[green]Conversation history cleared[/green]")
        
    elif cmd == "status":
        status = coordinator.get_system_status()
        console.print(Panel(
            f"[bold]System Status:[/bold]\n\n"
            f"Active Agents: {len(status['active_agents'])}\n"
            f"Total Messages: {status['total_messages']}\n"
            f"Current Session: {status['session_id']}\n"
            f"Memory Usage: {status['memory_usage']} entries",
            title="Status",
            border_style="blue"
        ))
        
    elif cmd == "exit":
        console.print("[yellow]Goodbye![/yellow]")
        return True
        
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        
    return False


@cli.command()
@click.argument('message')
@click.option('--agent', '-a', help='Specific agent to use')
@click.pass_context
def ask(ctx, message: str, agent: Optional[str]):
    """Ask a single question to the agent system"""
    coordinator = ctx.obj['coordinator']
    
    async def single_ask():
        with Live(Spinner("dots", text="Processing..."), refresh_per_second=10):
            response = await coordinator.process_message(message, agent)
        
        if response.agent_used:
            console.print(f"[bold magenta]{response.agent_used.title()} Agent:[/bold magenta]")
            
        formatted_response = format_response(response.content)
        console.print(formatted_response)
        
        if response.tools_used:
            console.print(f"\n[dim]Tools used: {', '.join(response.tools_used)}[/dim]")
    
    asyncio.run(single_ask())


@cli.command()
@click.pass_context
def list_agents(ctx):
    """List all available agents and their capabilities"""
    coordinator = ctx.obj['coordinator']
    agents_info = coordinator.get_available_agents()
    
    console.print(Panel(
        "[bold]Available Agents:[/bold]",
        title="MCP Agent System",
        border_style="blue"
    ))
    
    for agent_name, agent_info in agents_info.items():
        display_agent_info(agent_name, agent_info)


if __name__ == "__main__":
    # Ensure API key is set
    if not os.getenv("OPENROUTER_API_KEY"):
        console.print("[red]Error: OPENROUTER_API_KEY environment variable must be set[/red]")
        sys.exit(1)
        
    cli()

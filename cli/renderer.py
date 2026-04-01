# -*- coding: utf-8 -*-
"""Rich-based output renderer for the REPL.

Handles Markdown rendering, syntax highlighting, tool output, and spinners.
"""
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.status import Status
from rich.text import Text
from rich.theme import Theme

_THEME = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "error": "bold red",
    "tool": "dim green",
    "agent": "bold blue",
})

console = Console(theme=_THEME)


def render_markdown(text: str) -> None:
    """Render markdown text to the terminal."""
    md = Markdown(text)
    console.print(md)


def render_tool_call(tool_name: str, args_summary: str) -> None:
    """Display a tool call notification."""
    console.print(
        f"  [tool]⚡ {tool_name}[/tool] {args_summary}",
    )


def render_tool_result(tool_name: str, output: str, is_error: bool = False) -> None:
    """Display tool execution result."""
    style = "error" if is_error else "dim"
    if len(output) > 2000:
        output = output[:2000] + "\n... (truncated)"
    console.print(Panel(
        Text(output, style=style),
        title=f"[tool]{tool_name}[/tool]",
        border_style="dim",
        expand=False,
    ))


def render_agent_message(text: str) -> None:
    """Render the agent's response."""
    render_markdown(text)


def render_error(message: str) -> None:
    """Display an error message."""
    console.print(f"[error]Error: {message}[/error]")


def render_info(message: str) -> None:
    """Display an info message."""
    console.print(f"[info]{message}[/info]")


def render_warning(message: str) -> None:
    """Display a warning message."""
    console.print(f"[warning]⚠ {message}[/warning]")


def create_spinner(message: str = "Thinking...") -> Status:
    """Create a spinner context manager."""
    return console.status(message, spinner="dots")


def render_welcome(model_name: str, provider: str) -> None:
    """Display the welcome banner — Claude Code style."""
    import os
    try:
        w = os.get_terminal_size().columns
    except OSError:
        w = 80

    console.print()
    console.print(f"[bold]╭{'─' * (w - 2)}╮[/bold]")
    console.print(f"[bold]│[/bold]  [bold cyan]CodeAgent[/bold cyan] v0.1.0{' ' * (w - 22)}[bold]│[/bold]")
    console.print(f"[bold]│[/bold]  Model: [cyan]{model_name}[/cyan] ({provider}){' ' * max(0, w - 14 - len(model_name) - len(provider))}[bold]│[/bold]")
    console.print(f"[bold]╰{'─' * (w - 2)}╯[/bold]")
    console.print()
    console.print(
        "[dim]  /help for commands · Ctrl+C to interrupt · shift+tab to switch mode[/dim]"
    )
    console.print()


def render_token_status(tokens: int, cost: float | None = None) -> str:
    """Format token/cost status for the toolbar."""
    parts = [f"tokens: {tokens:,}"]
    if cost is not None:
        parts.append(f"cost: ${cost:.4f}")
    return " | ".join(parts)

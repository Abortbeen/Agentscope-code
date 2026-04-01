# -*- coding: utf-8 -*-
"""Real-time TUI renderer for CodeAgent — Claude Code style.

Uses AgentScope's instance hooks to render agent activity in real-time:
- Animated thinking spinner (⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏)
- Tool call visualization with collapsible-style panels
- Esc key to interrupt thinking
- Claude Code-inspired visual style
"""
import asyncio
import random
import sys
import threading
import time
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

from agentscope.message import Msg

_THEME = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "error": "bold red",
    "tool.name": "bold cyan",
    "tool.arg": "dim",
    "tool.result": "dim",
    "thinking": "dim magenta",
    "agent": "bold",
    "step": "dim yellow",
})

console = Console(theme=_THEME)

# Braille spinner frames (same as Claude Code)
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# Claude Code spinner verbs — randomly picked for each turn
_SPINNER_VERBS = [
    "Thinking", "Brewing", "Churning", "Cogitating", "Computing",
    "Cooking", "Crafting", "Crystallizing", "Deliberating", "Fermenting",
    "Forging", "Generating", "Hatching", "Ideating", "Imagining",
    "Inferring", "Kneading", "Manifesting", "Marinating", "Mulling",
    "Musing", "Orchestrating", "Percolating", "Pondering", "Processing",
    "Ruminating", "Simmering", "Sketching", "Synthesizing", "Tinkering",
    "Weaving", "Whirring", "Working", "Architecting", "Composing",
    "Concocting", "Contemplating", "Cultivating", "Gesticulating",
    "Noodling", "Philosophising", "Spelunking", "Vibing", "Wrangling",
    "Bootstrapping", "Cascading", "Channeling", "Harmonizing",
    "Transmuting", "Unravelling", "Zigzagging", "Clauding",
]

def _pick_verb() -> str:
    """Pick a random spinner verb."""
    return random.choice(_SPINNER_VERBS)


class _ThinkingSpinner:
    """Animated thinking spinner that runs in a background thread.

    Uses raw ANSI escape sequences to update in-place,
    matching the Claude Code spinner style. Also renders a mini status bar
    below the spinner so context persists during agent processing.

    Captures keyboard input during spinning so users can type ahead.
    The typed text is shown in the ❯ prompt line and returned via
    `get_type_ahead()` after stopping.
    """

    _CR = "\r"
    _CLEAR_LINE = "\033[2K"

    def __init__(self, con: Console, label: str = "Thinking",
                 status_fn=None) -> None:
        self._console = con
        self._label = label
        self._running = False
        self._thread: threading.Thread | None = None
        self._input_thread: threading.Thread | None = None
        self._frame_idx = 0
        self._status_fn = status_fn  # callable returning status lines string
        self._lines_written = 0
        self._type_ahead: list[str] = []  # captured keystrokes
        self._old_term_settings = None

    def start(self) -> None:
        self._running = True
        self._type_ahead.clear()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
        # Start non-blocking keyboard capture
        self._input_thread = threading.Thread(target=self._capture_input, daemon=True)
        self._input_thread.start()

    def stop(self) -> None:
        self._running = False
        # Restore terminal settings FIRST
        self._restore_terminal()
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
        if self._input_thread:
            self._input_thread.join(timeout=0.2)
            self._input_thread = None
        # Clear all lines we wrote (spinner + status)
        for _ in range(self._lines_written):
            sys.stdout.write(f"\033[A{self._CLEAR_LINE}")
        sys.stdout.write(f"{self._CLEAR_LINE}{self._CR}")
        sys.stdout.flush()
        self._lines_written = 0

    def get_type_ahead(self) -> str:
        """Return any text typed during spinning."""
        return "".join(self._type_ahead)

    def update_label(self, label: str) -> None:
        self._label = label

    def _restore_terminal(self) -> None:
        """Restore terminal to original settings."""
        if self._old_term_settings is not None:
            try:
                import termios
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN,
                                  self._old_term_settings)
            except Exception:
                pass
            self._old_term_settings = None

    def _capture_input(self) -> None:
        """Read keystrokes in raw mode without blocking the spinner."""
        try:
            import termios, tty, select
            fd = sys.stdin.fileno()
            self._old_term_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            while self._running:
                rlist, _, _ = select.select([fd], [], [], 0.05)
                if rlist:
                    ch = sys.stdin.read(1)
                    if ch == '\x7f' or ch == '\x08':  # backspace
                        if self._type_ahead:
                            self._type_ahead.pop()
                    elif ch >= ' ':  # printable
                        self._type_ahead.append(ch)
        except Exception:
            pass  # Not a TTY or termios unavailable

    def _animate(self) -> None:
        while self._running:
            frame = _SPINNER_FRAMES[self._frame_idx % len(_SPINNER_FRAMES)]

            # Clear all previously written lines
            if self._lines_written > 0:
                for _ in range(self._lines_written):
                    sys.stdout.write(f"\033[A{self._CLEAR_LINE}")
            sys.stdout.write(f"{self._CLEAR_LINE}{self._CR}")

            # Build full layout: spinner → status (which includes separator)
            output = f"{frame} {self._label}..."
            lines = 0

            if self._status_fn:
                try:
                    status = self._status_fn()
                    if status:
                        # Inject type-ahead text into the ❯ line
                        typed = "".join(self._type_ahead)
                        if typed:
                            status = status.replace("❯", f"❯ {typed}")
                        output += f"\n{status}"
                        lines += status.count("\n") + 1
                except Exception:
                    pass

            sys.stdout.write(output)
            sys.stdout.flush()
            self._lines_written = lines
            self._frame_idx += 1
            time.sleep(0.08)


class RealtimeTUI:
    """Real-time TUI with Claude Code-style rendering.

    Features:
    - Animated braille spinner during thinking
    - Tool calls shown as: ⚡ ToolName args
    - Tool results in dim panels
    - Esc to interrupt (via asyncio.Event)
    - Clean markdown rendering for final output
    """

    def __init__(self, con: Console | None = None, status_fn=None) -> None:
        self._console = con or console
        self._iteration = 0
        self._hooks_registered = False
        self._spinner: _ThinkingSpinner | None = None
        self._interrupted = asyncio.Event()
        self._status_fn = status_fn  # callable returning ANSI status string

    def _start_spinner(self, label: str = "Thinking") -> None:
        """Start or update the thinking spinner."""
        if self._spinner:
            self._spinner.stop()
        self._spinner = _ThinkingSpinner(
            self._console, label, status_fn=self._status_fn,
        )
        self._spinner.start()

    # Track files read and tools used for Claude-style display
    _files_read: list[str] = []
    _tools_used: int = 0

    def _stop_spinner(self) -> None:
        """Stop the thinking spinner."""
        if self._spinner:
            self._spinner.stop()
            self._spinner = None

    def get_type_ahead(self) -> str:
        """Return text typed during spinner."""
        if self._spinner:
            return self._spinner.get_type_ahead()
        return ""

    def _register_hooks(self, react_agent) -> None:
        """Register rendering hooks on the agent instance."""
        if self._hooks_registered:
            return

        tui = self

        async def _on_pre_reasoning(agent, normalized_kwargs):
            tui._iteration += 1
            tui._turn_verb = _pick_verb()
            if tui._iteration == 1:
                tui._start_spinner(f"{tui._turn_verb}")
            else:
                tui._start_spinner(f"{tui._turn_verb} (step {tui._iteration})")
            return None

        async def _on_post_reasoning(agent, normalized_kwargs, output):
            tui._stop_spinner()
            if output is None:
                return None
            if isinstance(output, Msg):
                content = output.content
                blocks = content if isinstance(content, list) else [content]
                for block in blocks:
                    if isinstance(block, dict):
                        btype = block.get("type", "")
                        if btype == "thinking":
                            thinking = block.get("thinking", "")
                            if thinking:
                                short = thinking[:120] + ("…" if len(thinking) > 120 else "")
                                tui._console.print(f"[dim]* {short}[/dim]")
                        elif btype == "tool_use":
                            tool_name = block.get("name", "unknown")
                            tool_input = block.get("input", {})
                            tui._tools_used += 1

                            # Claude Code style: ● ToolName with tree connector for details
                            if tool_name in ("FileRead", "Read"):
                                fpath = tool_input.get("file_path", "")
                                fname = fpath.split("/")[-1] if fpath else "file"
                                tui._files_read.append(fname)
                                tui._console.print(
                                    f"[bold cyan]●[/bold cyan] [dim]Reading {len(tui._files_read)} file{'s' if len(tui._files_read) > 1 else ''}…[/dim]"
                                )
                                tui._console.print(f"  [dim]⎿  {fname}[/dim]")
                            elif tool_name in ("Bash", "bash_execute"):
                                cmd = str(tool_input.get("command", ""))[:80]
                                tui._console.print(
                                    f"[bold cyan]●[/bold cyan] [dim]Running…[/dim]"
                                )
                                tui._console.print(f"  [dim]⎿  $ {cmd}[/dim]")
                            elif tool_name in ("FileWrite", "FileEdit", "Write", "Edit"):
                                fpath = tool_input.get("file_path", "")
                                fname = fpath.split("/")[-1] if fpath else "file"
                                tui._console.print(
                                    f"[bold cyan]●[/bold cyan] [dim]Editing {fname}…[/dim]"
                                )
                                tui._console.print(f"  [dim]⎿  {fpath}[/dim]")
                            else:
                                summary = _format_tool_input(tool_name, tool_input)
                                tui._console.print(
                                    f"[bold cyan]●[/bold cyan] [dim]{tool_name}…[/dim]"
                                )
                                if summary:
                                    tui._console.print(f"  [dim]⎿  {summary}[/dim]")
            return None

        async def _on_post_acting(agent, normalized_kwargs, output):
            return None

        try:
            react_agent.register_instance_hook(
                "pre_reasoning", "tui_pre_reasoning", _on_pre_reasoning,
            )
            react_agent.register_instance_hook(
                "post_reasoning", "tui_post_reasoning", _on_post_reasoning,
            )
            react_agent.register_instance_hook(
                "post_acting", "tui_post_acting", _on_post_acting,
            )
            self._hooks_registered = True
        except Exception as e:
            self._console.print(f"[warning]TUI hooks unavailable: {e}[/warning]")

    def _unregister_hooks(self, react_agent) -> None:
        """Remove TUI hooks from the agent."""
        try:
            react_agent.remove_instance_hook("pre_reasoning", "tui_pre_reasoning")
            react_agent.remove_instance_hook("post_reasoning", "tui_post_reasoning")
            react_agent.remove_instance_hook("post_acting", "tui_post_acting")
        except Exception:
            pass
        self._hooks_registered = False

    async def run_with_agent(self, agent, user_input: str) -> Msg | None:
        """Run agent with real-time Claude Code-style TUI rendering.

        Args:
            agent: CodingAgent instance.
            user_input: User's message.

        Returns:
            The final Msg from the agent.
        """
        # Clear prompt_toolkit leftovers, then rewrite layout:
        # spinner → separator → ❯ input → status bar
        sys.stdout.write("\033[J")  # clear from cursor to end of screen
        sys.stdout.flush()
        self._user_input_text = user_input  # save for layout redraw

        react_agent = agent.agent
        self._iteration = 0
        self._interrupted.clear()
        self._files_read = []
        self._tools_used = 0
        self._turn_verb = _pick_verb()

        self._register_hooks(react_agent)

        original_disable = react_agent._disable_console_output
        react_agent._disable_console_output = True

        _start_time = time.time()

        try:
            result_msg = await agent.reply(user_input)

            self._stop_spinner()

            if result_msg:
                self._render_final(result_msg)

            # Show processing time with random verb (Claude Code style)
            elapsed = time.time() - _start_time
            verb = getattr(self, '_turn_verb', _pick_verb())
            # Convert "Thinking" → "Thought", "Brewing" → "Brewed", etc.
            if verb.endswith("ing"):
                past = verb[:-3] + "ed"  # Brew+ed, Churn+ed
                if verb.endswith("ting"):
                    past = verb[:-4] + "ted"  # Cogita+ted
                elif verb.endswith("king"):
                    past = verb[:-4] + "ked"  # Think → Thinked? No...
            else:
                past = verb + "d"
            # Special cases for natural English
            _PAST_MAP = {
                "Thinking": "Thought", "Brewing": "Brewed", "Churning": "Churned",
                "Computing": "Computed", "Cooking": "Cooked", "Crafting": "Crafted",
                "Forging": "Forged", "Weaving": "Wove", "Vibing": "Vibed",
                "Clauding": "Clauded", "Philosophising": "Philosophised",
            }
            past = _PAST_MAP.get(verb, past)
            if elapsed >= 1:
                self._console.print(f"\n[dim]✻ {past} for {elapsed:.0f}s[/dim]\n")
            else:
                self._console.print()

            return result_msg
        except asyncio.CancelledError:
            self._stop_spinner()
            self._console.print("\n[dim]Interrupted.[/dim]")
            return None
        finally:
            self._stop_spinner()
            react_agent._disable_console_output = original_disable
            self._unregister_hooks(react_agent)

    def _render_final(self, msg: Msg) -> None:
        """Render the final agent response in Claude Code style with ● prefix."""
        if not msg.content:
            return

        content = msg.content
        if isinstance(content, str):
            self._console.print()
            self._console.print("[bold cyan]●[/bold cyan]", end=" ")
            self._console.print(Markdown(content))
            return

        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type", "")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        # Already rendered by hook
                        pass
                    elif btype == "tool_result":
                        self._render_tool_result(block)
                elif isinstance(block, str):
                    text_parts.append(block)

            full_text = "\n".join(t for t in text_parts if t.strip())
            if full_text:
                self._console.print()
                self._console.print("[bold cyan]●[/bold cyan]", end=" ")
                self._console.print(Markdown(full_text))

    def _render_tool_result(self, block: dict) -> None:
        """Render a tool result in a compact panel."""
        tool_name = block.get("name", "tool")
        output_blocks = block.get("output", block.get("content", []))
        is_error = block.get("is_error", False)

        output_text = ""
        if isinstance(output_blocks, list):
            for sub in output_blocks:
                if isinstance(sub, dict) and sub.get("type") == "text":
                    output_text += sub.get("text", "")
                elif isinstance(sub, str):
                    output_text += sub
        elif isinstance(output_blocks, str):
            output_text = output_blocks

        if output_text:
            if len(output_text) > 1500:
                output_text = (
                    output_text[:750]
                    + "\n  ... (truncated) ...\n"
                    + output_text[-750:]
                )

            style = "red" if is_error else "dim"
            border = "red" if is_error else "dim"
            self._console.print(Panel(
                Text(output_text, style=style, overflow="fold"),
                title=f"[tool.name]{tool_name}[/tool.name]",
                border_style=border,
                expand=False,
                width=min(100, self._console.width - 4),
                padding=(0, 1),
            ))


def _format_tool_input(tool_name: str, tool_input: Any) -> str:
    """Format tool input for display — show the most relevant argument."""
    if isinstance(tool_input, dict):
        # Priority order of fields to display
        for key in ("command", "file_path", "pattern", "query", "url",
                     "prompt", "message", "name", "subject", "expression"):
            if key in tool_input:
                val = str(tool_input[key])
                return val[:120] + ("..." if len(val) > 120 else "")
        return str(tool_input)[:120]
    return str(tool_input)[:120]


def create_tui(con: Console | None = None) -> RealtimeTUI:
    """Create a RealtimeTUI instance."""
    return RealtimeTUI(con)

# -*- coding: utf-8 -*-
"""Main REPL loop for CodeAgent.

Uses prompt_toolkit for input and rich for output rendering.
Wires together: Agent, Toolkit, Permissions, Sessions, Skills, Hooks, Token tracking.
"""
import asyncio
import os
import signal
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML, FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.patch_stdout import patch_stdout

from .commands import CommandRegistry
from .renderer import (
    console,
    render_welcome,
    render_agent_message,
    render_error,
    render_info,
    render_tool_call,
    render_tool_result,
    render_markdown,
    create_spinner,
    render_token_status,
    render_warning,
)


# ── Agent modes (like Claude Code: Auto / Plan / Manual) ──────────────
_MODES = ["Auto", "Plan", "Manual"]

_MODE_DESCRIPTIONS = {
    "Auto": "Agent runs tools automatically",
    "Plan": "Agent proposes plan, asks before acting",
    "Manual": "Agent suggests commands, you run them",
}

class _ModeManager:
    """Tracks the current agent interaction mode."""

    def __init__(self) -> None:
        self._index = 0  # Start with Auto

    @property
    def current(self) -> str:
        return _MODES[self._index]

    @property
    def description(self) -> str:
        return _MODE_DESCRIPTIONS[self.current]

    def cycle(self) -> str:
        """Cycle to next mode. Returns new mode name."""
        self._index = (self._index + 1) % len(_MODES)
        return self.current


# ── prompt_toolkit style (Claude Code palette) ──────────────────────
_PT_STYLE = PTStyle.from_dict({
    "prompt": "bold #b4a0ff",           # Soft purple for ❯
    "mode-auto": "bold #60d394",        # Green
    "mode-plan": "bold #f9c74f",        # Yellow
    "mode-manual": "bold #f4845f",      # Orange
    "separator": "#555555",             # Dim gray line
    "bottom-toolbar": "noreverse",      # Remove default reverse background
    "toolbar": "#888888 noreverse",     # Dim toolbar text, no bg
    "toolbar.key": "#b4a0ff noreverse", # Purple for keyhints
    "toolbar.mode": "bold #60d394 noreverse",  # Green mode label
    "toolbar.model": "#5dadec noreverse",      # Blue model name
    "toolbar.cost": "#888888 noreverse",       # Dim cost
    # Completion dropdown styling
    "completion-menu": "bg:#1e1e2e #cdd6f4",                    # Dark bg, light text
    "completion-menu.completion": "bg:#1e1e2e #cdd6f4",          # Normal item
    "completion-menu.completion.current": "bg:#45475a #cdd6f4",  # Selected item
    "completion-menu.meta": "bg:#1e1e2e #888888",                # Description dim
    "completion-menu.meta.completion": "bg:#1e1e2e #888888",
    "completion-menu.meta.completion.current": "bg:#45475a #b4befe",  # Selected desc
})


class SlashCompleter(Completer):
    """Autocomplete for /commands and /skills with preview descriptions.

    Triggers when the input starts with '/'. Shows a dropdown with:
    - Built-in commands (from CommandRegistry)
    - Skills (from SkillRegistry)
    - Agent types (from AgentDefinitionLoader)

    Each entry shows a description in the meta column.
    """

    def __init__(self) -> None:
        self._commands: dict[str, str] = {}   # name -> description
        self._skills: dict[str, str] = {}
        self._agents: dict[str, str] = {}

    def set_commands(self, commands_registry) -> None:
        """Populate from CommandRegistry."""
        self._commands = {
            name: info.get("description", "")
            for name, info in commands_registry._commands.items()
        }

    def set_skills(self, skill_registry) -> None:
        """Populate from SkillRegistry."""
        self._skills = {
            s.name: s.description
            for s in skill_registry.list_skills()
        }

    def set_agents(self, agent_defs: list) -> None:
        """Populate from agent definitions."""
        self._agents = {
            d.name: d.description
            for d in agent_defs
        }

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()

        # Only complete when starting with /
        if not text.startswith("/"):
            return

        # The part after /
        prefix = text[1:]

        # Commands first
        for name, desc in sorted(self._commands.items()):
            if name.startswith(prefix):
                yield Completion(
                    f"/{name}",
                    start_position=-len(text),
                    display=f"/{name}",
                    display_meta=desc[:60] if desc else "",
                )

        # Skills
        for name, desc in sorted(self._skills.items()):
            if name.startswith(prefix):
                yield Completion(
                    f"/{name}",
                    start_position=-len(text),
                    display=f"/{name}",
                    display_meta=f"[skill] {desc[:50]}" if desc else "[skill]",
                )

        # Agents (spawn via /agent:<name>)
        agent_prefix = prefix[len("agent:"):] if prefix.startswith("agent:") else None
        if agent_prefix is not None or prefix == "" or "agent".startswith(prefix):
            for name, desc in sorted(self._agents.items()):
                if agent_prefix is None or name.startswith(agent_prefix):
                    yield Completion(
                        f"/agent:{name}",
                        start_position=-len(text),
                        display=f"/agent:{name}",
                        display_meta=f"[agent] {desc[:50]}" if desc else "[agent]",
                    )


from ..config.settings import CodeAgentConfig
from ..agent.coding_agent import CodingAgent
from ..tools.registry import register_all_tools
from ..tools.ask_user_tool import set_ask_user_callback
from ..utils.git import get_git_info
from ..agent.system_prompt import SystemPromptBuilder
from ..permissions.checker import PermissionChecker
from ..session.manager import SessionManager
from ..skills.registry import SkillRegistry
from ..skills.loader import SkillLoader
from ..hooks.engine import HookEngine
from ..observability.cost_display import TokenTracker
from ..scheduler.background import BackgroundTaskManager
from ..tools.agent_tool import set_parent_context
from ..tools.team_tools import set_team_context
from ..observability.tracing import init_observability
from .tui import RealtimeTUI

# ── Suppress ALL agentscope studio/tracing output ──────────────────
import logging as _logging

# agentscope uses logger named "as" (not "agentscope"!)
# Silence it completely
_as_logger = _logging.getLogger("as")
_as_logger.setLevel(_logging.CRITICAL)
_as_logger.propagate = False
_as_logger.handlers.clear()

# Also silence the "agentscope" namespace just in case
for _logger_name in ("agentscope", "agentscope._studio_hooks",
                      "agentscope.studio"):
    _lg = _logging.getLogger(_logger_name)
    _lg.setLevel(_logging.CRITICAL)
    _lg.propagate = False
    _lg.handlers.clear()


def _nuke_studio_hooks():
    """Completely disable studio hooks — call after every agent creation."""
    # 1. Monkey-patch the hook function itself to be a no-op
    try:
        import agentscope._studio_hooks as _sh
        _sh.as_studio_forward_message_pre_print_hook = lambda *a, **kw: None
        # Also patch any other studio functions
        for attr in dir(_sh):
            if callable(getattr(_sh, attr, None)) and "studio" in attr.lower():
                setattr(_sh, attr, lambda *a, **kw: None)
    except Exception:
        pass

    # 2. Remove all studio hooks from AgentBase class-level hooks
    try:
        from agentscope.agent import AgentBase
        _ALL_HOOK_TYPES = [
            "pre_print", "post_print", "pre_reply", "post_reply",
            "pre_observe", "post_observe", "pre_reasoning",
            "post_reasoning", "pre_acting", "post_acting",
        ]
        for hook_type in _ALL_HOOK_TYPES:
            class_hooks = getattr(AgentBase, f"_class_{hook_type}_hooks", {})
            stale = [k for k in class_hooks
                     if "studio" in k.lower() or "forward" in k.lower()]
            for k in stale:
                del class_hooks[k]
    except Exception:
        pass

    # 3. Disable studio connection flags
    try:
        import agentscope
        agentscope._studio_url = None
        agentscope._studio_active = False
    except Exception:
        pass
    try:
        from agentscope import _runtime
        _runtime._studio_url = None
    except Exception:
        pass

_nuke_studio_hooks()


class _TrackedModel:
    """Proxy that wraps a model to capture token usage from ChatResponse."""

    def __init__(self, model, tracker: TokenTracker):
        self._inner = model
        self._tracker = tracker

    def __getattr__(self, name):
        return getattr(self._inner, name)

    async def __call__(self, *args, **kwargs):
        result = await self._inner(*args, **kwargs)
        # Handle streaming: wrap the async generator
        if hasattr(result, '__aiter__'):
            tracker = self._tracker

            async def _tracking_stream():
                last_chunk = None
                async for chunk in result:
                    last_chunk = chunk
                    yield chunk
                if last_chunk is not None and hasattr(last_chunk, 'usage') and last_chunk.usage:
                    tracker.add(
                        input_tokens=getattr(last_chunk.usage, 'input_tokens', 0) or 0,
                        output_tokens=getattr(last_chunk.usage, 'output_tokens', 0) or 0,
                    )
            return _tracking_stream()
        # Non-streaming: extract usage directly
        if hasattr(result, 'usage') and result.usage:
            self._tracker.add(
                input_tokens=getattr(result.usage, 'input_tokens', 0) or 0,
                output_tokens=getattr(result.usage, 'output_tokens', 0) or 0,
            )
        return result


def _wrap_model_for_tracking(agent, token_tracker: TokenTracker) -> None:
    """Replace agent's model with a tracking proxy."""
    inner_agent = getattr(agent, '_agent', None)
    if inner_agent is None:
        return
    model = getattr(inner_agent, 'model', None)
    if model is None:
        return
    tracked = _TrackedModel(model, token_tracker)
    inner_agent.model = tracked
    # Also update the outer reference
    if hasattr(agent, '_model'):
        agent._model = tracked


async def _create_agent(
    config: CodeAgentConfig,
    ask_callback=None,
) -> tuple[CodingAgent, dict]:
    """Create and initialize the CodingAgent with all tools and integrations.

    Returns:
        Tuple of (agent, context_dict) where context_dict holds references
        to all subsystems for commands and lifecycle management.
    """
    # --- 1. Register all tools into Toolkit ---
    toolkit = register_all_tools()

    # --- 2. Set up permission checker as middleware ---
    perm_checker = PermissionChecker(
        config=config.permissions,
        ask_callback=ask_callback,
    )

    # --- 3. Load skills ---
    skill_registry = SkillRegistry()
    skill_loader = SkillLoader(skill_registry)
    skill_count = skill_loader.load_all()

    # Register skill invocation tool if skills exist
    if skill_count > 0:
        from ..skills.skill_tool import invoke_skill, set_registry as set_skill_registry
        set_skill_registry(skill_registry)
        toolkit.register_tool_function(
            tool_func=invoke_skill,
            func_name="InvokeSkill",
            func_description="Invoke a registered skill by name.",
            group_name="basic",
            namesake_strategy="skip",
        )

    # --- 4. Set up hook engine ---
    hook_engine = HookEngine(config.hooks if config.hooks else None)

    # --- 5. Set up session manager ---
    session_mgr = SessionManager(
        storage_dir=config.session.storage_dir,
    )

    # --- 6. Set up token tracker ---
    token_tracker = TokenTracker(model_name=config.model.model_name)

    # --- 7. Set up background task manager ---
    bg_task_mgr = BackgroundTaskManager()

    # --- 8. Gather project context ---
    git_info = await get_git_info()
    project_memory = SystemPromptBuilder.load_project_memory()

    # Build extra context from skills
    skills_summary = skill_registry.get_skills_summary()

    # --- 9. Create the coding agent ---
    agent = CodingAgent(
        model_config=config.model,
        permissions_config=config.permissions,
        toolkit=toolkit,
        git_info=git_info,
        project_memory=project_memory,
        max_iters=30,
    )

    # Set parent context for sub-agent spawning and team creation
    set_parent_context(toolkit, config.model)
    set_team_context(toolkit, config.model)

    # Update system prompt with skills info if available
    if skills_summary:
        agent.update_system_prompt(
            git_info=git_info,
            project_memory=project_memory,
            extra_context=skills_summary,
        )

    # --- 10. Start skill file watcher ---
    try:
        skill_loader.start_watching()
    except Exception:
        pass  # Non-critical

    # Build context dict for commands and lifecycle
    context = {
        "config": config,
        "agent": agent,
        "toolkit": toolkit,
        "perm_checker": perm_checker,
        "skill_registry": skill_registry,
        "skill_loader": skill_loader,
        "hook_engine": hook_engine,
        "session_mgr": session_mgr,
        "token_tracker": token_tracker,
        "bg_task_mgr": bg_task_mgr,
        "git_info": git_info,
    }

    return agent, context


def _get_history_path() -> str:
    """Get the path for prompt history file."""
    from pathlib import Path
    history_dir = Path.home() / ".config" / "codeagent"
    history_dir.mkdir(parents=True, exist_ok=True)
    return str(history_dir / "history")


async def run_repl(
    config: CodeAgentConfig,
    initial_prompt: str | None = None,
    resume_session: str | None = None,
) -> None:
    """Run the main REPL loop.

    Args:
        config: The merged configuration.
        initial_prompt: Optional initial prompt for non-interactive mode.
        resume_session: Optional session ID to resume.
    """
    # Display welcome
    render_welcome(config.model.model_name, config.model.provider)

    # Set up AskUser callback early (needed for permissions)
    async def ask_user_callback(question: str) -> str:
        """Callback for AskUser tool and permission prompts."""
        console.print(f"\n[bold yellow]Agent asks:[/bold yellow] {question}")
        response = input("> ")
        return response

    set_ask_user_callback(ask_user_callback)

    # Create agent with all integrations
    render_info("Initializing agent...")
    try:
        agent, ctx = await _create_agent(config, ask_callback=ask_user_callback)
        _nuke_studio_hooks()  # Re-nuke after agent creation

        # Wrap model.__call__ to capture token usage
        _wrap_model_for_tracking(agent, ctx["token_tracker"])
    except Exception as e:
        render_error(f"Failed to initialize agent: {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return

    # Initialize observability (Studio + Tracing)
    if config.studio.enabled or config.tracing.enabled:
        obs_result = init_observability(
            studio_url=config.studio.url,
            auto_launch_studio=config.studio.auto_launch,
            studio_port=config.studio.port,
            tracing_url=config.tracing.url,
            project="codeagent",
        )
        if obs_result.get("studio_connected"):
            render_info(f"Studio connected: {obs_result['studio_url']}")
        if obs_result.get("tracing_enabled"):
            render_info("Tracing enabled")

    # Initialize A2A server
    a2a_server = None
    if config.a2a.enabled:
        try:
            from ..a2a import A2AServer, build_agent_card

            tool_names_for_card = list(agent.toolkit.tools.keys())
            card = build_agent_card(config.a2a, tools=tool_names_for_card)

            async def a2a_task_handler(prompt: str) -> str:
                """Handle A2A task by running through the agent."""
                from agentscope.message import Msg, TextBlock
                result_msg = await agent.reply(prompt)
                if isinstance(result_msg, Msg):
                    if isinstance(result_msg.content, str):
                        return result_msg.content
                    elif isinstance(result_msg.content, list):
                        texts = [b.text for b in result_msg.content if isinstance(b, TextBlock)]
                        return "\n".join(texts)
                return str(result_msg) if result_msg else "(no response)"

            a2a_server = A2AServer(
                agent_card=card,
                task_handler=a2a_task_handler,
                host=config.a2a.host,
                port=config.a2a.port,
            )
            await a2a_server.start()
            render_info(
                f"A2A server: http://{config.a2a.host}:{config.a2a.port} "
                f"| Agent Card: /.well-known/agent.json"
            )
        except Exception as e:
            render_warning(f"A2A server failed to start: {e}")

    ctx["a2a_server"] = a2a_server

    # Load agent definitions (for system prompt + info display)
    from ..agent.agent_loader import AgentDefinitionLoader
    agent_loader = AgentDefinitionLoader()
    agent_defs = agent_loader.load_all()
    ctx["agent_loader"] = agent_loader

    # Report ready
    tool_names = list(agent.toolkit.tools.keys())
    skill_count = len(ctx["skill_registry"].list_skills())
    agent_count = len(agent_defs)
    render_info(
        f"Ready! Model: {config.model.model_name} | "
        f"Tools: {len(tool_names)} | "
        f"Skills: {skill_count} | "
        f"Agents: {agent_count}"
    )

    # Handle session resume
    session_mgr: SessionManager = ctx["session_mgr"]
    if resume_session:
        session_data = session_mgr.load_session(resume_session)
        if session_data:
            render_info(f"Resumed session: {resume_session}")
        else:
            render_warning(f"Session '{resume_session}' not found, starting fresh.")

    # Create new session
    session_id = session_mgr.create_session()

    # ── Mode manager ──
    mode_mgr = _ModeManager()
    ctx["mode_mgr"] = mode_mgr

    # ── Key bindings ──
    bindings = KeyBindings()

    @bindings.add("s-tab")
    def _cycle_mode(event):
        """Shift+Tab cycles through Auto / Plan / Manual."""
        new_mode = mode_mgr.cycle()
        event.app.invalidate()

    @bindings.add("tab")
    def _tab_complete(event):
        """Tab directly accepts the current completion into the input.

        - If completion menu is open → accept selected item
        - If no menu but completions available → insert first match
        - Otherwise → do nothing
        """
        buf = event.app.current_buffer
        if buf.complete_state:
            # Menu is open — accept current selection
            buf.complete_state = None  # close menu, text already inserted
        else:
            # Trigger completion and auto-accept first match
            buf.start_completion()
            if buf.complete_state:
                buf.complete_state = None

    # ── Build HUD toolbar (Claude Code style) ──
    token_tracker: TokenTracker = ctx["token_tracker"]
    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80

    def _get_term_width() -> int:
        try:
            return os.get_terminal_size().columns
        except OSError:
            return 80

    def _build_prompt():
        """❯ prompt (separator printed separately before prompt_async)."""
        mode = mode_mgr.current
        mode_prefix = "plan❯ " if mode == "Plan" else "manual❯ " if mode == "Manual" else "❯ "
        mode_class = (
            "class:mode-plan" if mode == "Plan"
            else "class:mode-manual" if mode == "Manual"
            else "class:prompt"
        )
        return FormattedText([(mode_class, mode_prefix)])

    import time as _time
    _session_start = _time.time()
    ctx["_session_start"] = _session_start

    def _build_toolbar():
        """Multi-line status bar (Claude Code style)."""
        mode = mode_mgr.current
        model_short = config.model.model_name.split("/")[-1]
        cost = token_tracker.estimated_cost
        cost_str = f"${cost:.4f}" if cost is not None else "$0.00"

        # Git branch info
        git_info = ctx.get("git_info")
        branch = git_info.branch if git_info and git_info.branch else "no-git"

        # Session duration
        elapsed = int(_time.time() - _session_start)
        if elapsed < 60:
            session_str = f"{elapsed}s"
        else:
            session_str = f"{elapsed // 60}m"

        # Context usage bar
        max_ctx = config.model.max_tokens * 10
        usage_pct = min(100, int(token_tracker.total_tokens / max(max_ctx, 1) * 100))
        filled = usage_pct // 10
        bar = "█" * filled + "░" * (10 - filled)

        # Tool count
        tool_count = len(agent.toolkit.tools)

        # Mode symbol
        mode_sym = "⏵⏵" if mode == "Auto" else "⏸⏸" if mode == "Plan" else "⏹⏹"
        mode_label = (
            "auto edit on" if mode == "Auto"
            else "plan mode on" if mode == "Plan"
            else "manual mode on"
        )

        sep = "─" * _get_term_width()
        return FormattedText([
            ("class:separator", sep + "\n"),
            # Line 1: branch
            ("class:toolbar", f"  branch:{branch}\n"),
            # Line 2: session stats (Claude Code style)
            ("class:toolbar", "  "),
            ("class:toolbar.model", model_short),
            ("class:toolbar", f" | session:{session_str}"
                              f" | input tokens:{token_tracker.input_tokens:,}"
                              f" output tokens:{token_tracker.output_tokens:,}"
                              f" cost:{cost_str}"),
            ("class:toolbar", f" | ctx:[{bar}]{usage_pct}%"),
            ("class:toolbar", f" | 🔧{tool_count}"),
            ("class:toolbar", "\n"),
            # Line 3: mode
            ("class:toolbar.mode", f"  {mode_sym} {mode_label}"),
            ("class:toolbar.key", " (shift+tab to cycle)"),
        ])


    # ── Slash completer ──
    slash_completer = SlashCompleter()

    # ── Prompt session ──
    prompt_session: PromptSession = PromptSession(
        history=FileHistory(_get_history_path()),
        auto_suggest=AutoSuggestFromHistory(),
        completer=slash_completer,
        complete_while_typing=True,
        reserve_space_for_menu=1,
        multiline=False,
        key_bindings=bindings,
        style=_PT_STYLE,
    )

    commands = CommandRegistry()
    # Register extra commands
    _register_extra_commands(commands, ctx)

    # Populate completer with commands, skills, and agents
    slash_completer.set_commands(commands)
    slash_completer.set_skills(ctx["skill_registry"])
    slash_completer.set_agents(agent_defs)

    # Handle initial prompt (non-interactive mode)
    if initial_prompt:
        await _process_input(initial_prompt, agent, commands, ctx)
        # Save session
        session_mgr.save_session(
            session_id=session_id,
            metadata={"model": config.model.model_name, "mode": "non-interactive"},
        )
        return

    # Main REPL loop — agent runs in background, prompt stays active
    import time
    _last_ctrl_c = 0.0
    _agent_task: asyncio.Task | None = None
    _input_queue: list[str] = []

    async def _run_queued(text_: str) -> None:
        """Process input and then drain any queued messages."""
        await _process_input(text_, agent, commands, ctx)
        while _input_queue:
            next_text = _input_queue.pop(0)
            ctx["_current_input"] = next_text
            await _process_input(next_text, agent, commands, ctx)

    with patch_stdout():
        while True:
            try:
                # Separator line above ❯ (scrolls naturally with conversation)
                console.print(f"[dim]{'─' * _get_term_width()}[/dim]")

                # ❯ prompt with status toolbar below
                user_input = await prompt_session.prompt_async(
                    _build_prompt,
                    bottom_toolbar=_build_toolbar,
                )

                if not user_input or not user_input.strip():
                    continue

                stripped = user_input.strip()
                ctx["_current_input"] = stripped

                # If agent is busy, queue the input
                if _agent_task and not _agent_task.done():
                    _input_queue.append(stripped)
                    console.print("[dim]⏳ Queued — will process after current response.[/dim]")
                    continue

                # Process in background so prompt stays active
                _agent_task = asyncio.create_task(_run_queued(stripped))

            except KeyboardInterrupt:
                now = time.time()
                # Cancel running agent task on first Ctrl+C
                if _agent_task and not _agent_task.done():
                    _agent_task.cancel()
                    console.print("\n[dim]Response interrupted.[/dim]")
                    _last_ctrl_c = now
                    continue
                if now - _last_ctrl_c < 1.5:
                    # Double Ctrl+C within 1.5s → exit
                    session_mgr.save_session(
                        session_id=session_id,
                        metadata={"model": config.model.model_name},
                    )
                    render_info("Session saved. Goodbye!")
                    break
                else:
                    _last_ctrl_c = now
                    console.print("\n[dim]Press Ctrl+C again to exit.[/dim]")
                    continue
            except EOFError:
                # Ctrl+D also exits gracefully
                if _agent_task and not _agent_task.done():
                    _agent_task.cancel()
                session_mgr.save_session(
                    session_id=session_id,
                    metadata={"model": config.model.model_name},
                )
                render_info("Session saved. Goodbye!")
                break
            except SystemExit:
                if _agent_task and not _agent_task.done():
                    _agent_task.cancel()
                session_mgr.save_session(
                    session_id=session_id,
                    metadata={"model": config.model.model_name},
                )
                render_info("Session saved. Goodbye!")
                break
            except Exception as e:
                render_error(f"Unexpected error: {e}")

    # Cleanup
    try:
        ctx["skill_loader"].stop_watching()
    except Exception:
        pass

    # Stop A2A server
    if a2a_server:
        try:
            await a2a_server.stop()
        except Exception:
            pass


def _register_extra_commands(commands: CommandRegistry, ctx: dict) -> None:
    """Register additional commands that need subsystem access."""

    async def _cmd_sessions(args: str, cmd_ctx: dict) -> str:
        """List recent sessions."""
        session_mgr: SessionManager = ctx["session_mgr"]
        sessions = session_mgr.list_sessions(limit=10)
        if not sessions:
            return "No saved sessions."
        lines = ["# Recent Sessions\n"]
        for s in sessions:
            lines.append(
                f"- **{s['id']}** — {s.get('saved_at', 'unknown')} "
                f"({s.get('messages', 0)} messages)"
            )
        return "\n".join(lines)

    async def _cmd_skills(args: str, cmd_ctx: dict) -> str:
        """List available skills."""
        registry: SkillRegistry = ctx["skill_registry"]
        skills = registry.list_skills()
        if not skills:
            return "No skills loaded."
        lines = ["# Available Skills\n"]
        for s in skills:
            lines.append(f"- **{s.name}**: {s.description}")
        return "\n".join(lines)

    async def _cmd_tools(args: str, cmd_ctx: dict) -> str:
        """List available tools."""
        agent: CodingAgent = ctx["agent"]
        tool_names = sorted(agent.toolkit.tools.keys())
        lines = ["# Available Tools\n"]
        for name in tool_names:
            lines.append(f"- {name}")
        return "\n".join(lines)

    async def _cmd_tokens(args: str, cmd_ctx: dict) -> str:
        """Show token usage."""
        tracker: TokenTracker = ctx["token_tracker"]
        return f"Token usage: {tracker.format_status()}"

    async def _cmd_tasks(args: str, cmd_ctx: dict) -> str:
        """List tasks on the task board."""
        from ..tools.task_tools import task_list as _task_list
        result = await _task_list()
        return result.content[0].text

    async def _cmd_agents(args: str, cmd_ctx: dict) -> str:
        """List available agent types."""
        from ..agent.agent_loader import AgentDefinitionLoader
        loader = AgentDefinitionLoader()
        definitions = loader.load_all()
        if not definitions:
            return "No agent definitions found."
        lines = ["# Available Agents\n"]
        for d in sorted(definitions, key=lambda x: x.name):
            model_tag = f" ({d.model})" if d.model else ""
            lines.append(f"- **{d.name}**{model_tag}: {d.description}")
        return "\n".join(lines)

    async def _cmd_init(args: str, cmd_ctx: dict) -> str:
        """Initialize project config."""
        from pathlib import Path
        agent_dir = Path.cwd() / ".agent"
        agent_dir.mkdir(exist_ok=True)
        (agent_dir / "agents").mkdir(exist_ok=True)
        (agent_dir / "skills").mkdir(exist_ok=True)
        settings_path = agent_dir / "settings.json"
        if not settings_path.exists():
            import json
            settings_path.write_text(json.dumps({
                "model": {"provider": "anthropic", "model_name": "claude-sonnet-4-20250514"},
                "permissions": {"mode": "default"},
            }, indent=2))
        return (
            "✓ Initialized project:\n"
            f"  - {agent_dir}/settings.json\n"
            f"  - {agent_dir}/agents/  (place agent .md definitions here)\n"
            f"  - {agent_dir}/skills/  (place skill .md definitions here)"
        )

    async def _cmd_doctor(args: str, cmd_ctx: dict) -> str:
        """Run diagnostics."""
        from pathlib import Path
        import shutil
        lines = ["# Diagnostics\n"]

        # Check config
        config = ctx.get("config")
        lines.append(f"- Model: **{config.model.model_name}** ({config.model.provider})")
        lines.append(f"- Permission mode: **{config.permissions.mode}**")

        # Check tools
        agent_obj = ctx.get("agent")
        tool_count = len(agent_obj.toolkit.tools) if agent_obj else 0
        lines.append(f"- Tools registered: **{tool_count}**")

        # Check skills
        skill_count = len(ctx["skill_registry"].list_skills())
        lines.append(f"- Skills loaded: **{skill_count}**")

        # Check agents
        from ..agent.agent_loader import AgentDefinitionLoader
        loader = AgentDefinitionLoader()
        agent_defs = loader.load_all()
        lines.append(f"- Agent definitions: **{len(agent_defs)}**")

        # Check git
        git_ok = shutil.which("git") is not None
        lines.append(f"- git: {'✓' if git_ok else '✗ not found'}")

        # Check ripgrep
        rg_ok = shutil.which("rg") is not None
        lines.append(f"- ripgrep: {'✓' if rg_ok else '✗ not found (grep fallback)'}")

        return "\n".join(lines)

    async def _cmd_cost(args: str, cmd_ctx: dict) -> str:
        """Show detailed cost breakdown."""
        tracker: TokenTracker = ctx["token_tracker"]
        cost = tracker.estimated_cost
        return (
            f"# Cost Summary\n\n"
            f"- Model: **{tracker.model_name}**\n"
            f"- Input tokens: **{tracker.input_tokens:,}**\n"
            f"- Output tokens: **{tracker.output_tokens:,}**\n"
            f"- Total tokens: **{tracker.total_tokens:,}**\n"
            f"- API calls: **{tracker.total_calls}**\n"
            f"- Estimated cost: **${cost:.4f}**" if cost is not None else
            f"- Estimated cost: *unknown pricing for model*"
        )

    commands.register("sessions", _cmd_sessions, "List recent sessions")
    commands.register("skills", _cmd_skills, "List available skills")
    commands.register("tools", _cmd_tools, "List available tools")
    commands.register("tokens", _cmd_tokens, "Show token usage stats")
    commands.register("tasks", _cmd_tasks, "List task board items")
    commands.register("agents", _cmd_agents, "List available agent types")
    commands.register("init", _cmd_init, "Initialize project config")
    commands.register("doctor", _cmd_doctor, "Run diagnostics")
    commands.register("cost", _cmd_cost, "Show detailed cost breakdown")


async def _process_input(
    text: str,
    agent: CodingAgent,
    commands: CommandRegistry,
    ctx: dict,
) -> None:
    """Process a single user input (command or message)."""
    hook_engine: HookEngine = ctx["hook_engine"]

    # Check for slash commands
    if commands.is_command(text):
        try:
            result = await commands.execute(text, ctx)
            if result:
                render_markdown(result)
        except SystemExit:
            raise
        except Exception as e:
            render_error(f"Command error: {e}")
        return

    # ── Apply mode prefix to guide agent behavior ──
    mode_mgr: _ModeManager | None = ctx.get("mode_mgr")
    mode = mode_mgr.current if mode_mgr else "Auto"

    if mode == "Plan":
        text = (
            "[MODE: Plan — Do NOT execute any tools yet. "
            "Analyze the request and present a numbered step-by-step plan. "
            "Ask the user to confirm before proceeding.]\n\n" + text
        )
    elif mode == "Manual":
        text = (
            "[MODE: Manual — Do NOT execute tools automatically. "
            "Instead, suggest the exact commands/edits the user should run, "
            "formatted as code blocks.]\n\n" + text
        )

    # Fire PreReply hooks
    await hook_engine.trigger("PreReply", context={"user_input": text})

    # Build status function for spinner display
    # Current user input text (set by _process_input for spinner display)

    def _spinner_status():
        mode_mgr_ref = ctx.get("mode_mgr")
        tracker = ctx.get("token_tracker")
        cfg = ctx.get("config")
        git = ctx.get("git_info")
        if not cfg or not tracker:
            return None
        import os, time as _t
        try:
            w = os.get_terminal_size().columns
        except OSError:
            w = 80
        sep = "─" * w
        branch = git.branch if git and git.branch else "no-git"
        model_short = cfg.model.model_name.split("/")[-1]
        cost = tracker.estimated_cost
        cost_str = f"${cost:.4f}" if cost is not None else "$0.00"
        mode = mode_mgr_ref.current if mode_mgr_ref else "Auto"
        mode_sym = "⏵⏵" if mode == "Auto" else "⏸⏸" if mode == "Plan" else "⏹⏹"
        mode_label = "auto edit on" if mode == "Auto" else "plan mode on" if mode == "Plan" else "manual mode on"
        _start = ctx.get("_session_start", _t.time())
        elapsed = int(_t.time() - _start)
        session_str = f"{elapsed}s" if elapsed < 60 else f"{elapsed // 60}m"
        tool_count = len(ctx["agent"].toolkit.tools) if ctx.get("agent") else 0
        max_ctx = cfg.model.max_tokens * 10
        usage_pct = min(100, int(tracker.total_tokens / max(max_ctx, 1) * 100))
        filled = usage_pct // 10
        bar = "█" * filled + "░" * (10 - filled)
        # Full layout: separator → ❯ input → separator → status
        cur_input = ctx.get("_current_input", "")
        user_line = f"❯ {cur_input}" if cur_input else "❯"
        return (
            f"\033[2m{sep}\033[0m\n"
            f"\033[1;38;5;141m{user_line}\033[0m\n"
            f"\033[2m{sep}\033[0m\n"
            f"\033[38;5;243m  branch:{branch}\n"
            f"  {model_short} | session:{session_str}"
            f" | input tokens:{tracker.input_tokens:,}"
            f" output tokens:{tracker.output_tokens:,}"
            f" cost:{cost_str}"
            f" | ctx:[{bar}]{usage_pct}%"
            f" | 🔧{tool_count}\n"
            f"  {mode_sym} {mode_label} (shift+tab to cycle)\033[0m"
        )

    # Send to agent with real-time TUI rendering
    try:
        tui = RealtimeTUI(console, status_fn=_spinner_status)
        response_msg = await tui.run_with_agent(agent, text)

        if not response_msg:
            render_info("(No response from agent)")

        # Fire PostReply hooks
        await hook_engine.trigger("PostReply", context={"user_input": text})

    except KeyboardInterrupt:
        render_info("Response interrupted.")
    except Exception as e:
        render_error(f"Agent error: {e}")

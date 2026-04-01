# -*- coding: utf-8 -*-
"""Hook execution engine.

Supports three hook types: command (shell), prompt (LLM), http (webhook).
Integrates with AgentScope's agent hook system.

Implements R24-R27 from the plan.
"""
import asyncio
import fnmatch
from dataclasses import dataclass, field
from typing import Any, Literal

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ..config.schema import HookConfig


@dataclass
class HookResult:
    """Result from a hook execution."""
    success: bool
    output: str = ""
    error: str | None = None


class HookEngine:
    """Manages and executes hooks at various lifecycle points."""

    def __init__(self, hooks: list[HookConfig] | None = None) -> None:
        self._hooks: list[HookConfig] = list(hooks) if hooks else []
        self._once_executed: set[int] = set()

    def add_hook(self, hook: HookConfig) -> None:
        """Register a hook."""
        self._hooks.append(hook)

    def remove_hooks_by_event(self, event: str) -> None:
        """Remove all hooks for a given event."""
        self._hooks = [h for h in self._hooks if h.event != event]

    def _match_condition(
        self,
        hook: HookConfig,
        tool_name: str | None = None,
        args: dict | None = None,
    ) -> bool:
        """Check if a hook's condition matches the current context."""
        cond = hook.condition
        if cond is None:
            return True

        if cond.tool_name and tool_name:
            if not fnmatch.fnmatch(tool_name, cond.tool_name):
                return False

        if cond.pattern and args:
            args_str = str(args)
            if not fnmatch.fnmatch(args_str, cond.pattern):
                return False

        return True

    async def _execute_command_hook(self, hook: HookConfig, context: dict) -> HookResult:
        """Execute a command (shell) hook."""
        command = hook.command
        if not command:
            return HookResult(success=False, error="No command specified")

        # Substitute context variables in command
        for key, value in context.items():
            command = command.replace(f"${{{key}}}", str(value))

        timeout_sec = hook.timeout / 1000.0
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_sec,
            )
            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += f"\nSTDERR: {stderr.decode('utf-8', errors='replace')}"

            return HookResult(
                success=proc.returncode == 0,
                output=output,
                error=None if proc.returncode == 0 else f"Exit code: {proc.returncode}",
            )
        except asyncio.TimeoutError:
            return HookResult(success=False, error=f"Hook timed out after {timeout_sec}s")
        except Exception as e:
            return HookResult(success=False, error=str(e))

    async def _execute_prompt_hook(self, hook: HookConfig, context: dict) -> HookResult:
        """Execute a prompt (LLM) hook."""
        prompt = hook.prompt
        if not prompt:
            return HookResult(success=False, error="No prompt specified")

        # For now, return the prompt as a placeholder
        # Full implementation would call a small model
        return HookResult(
            success=True,
            output=f"[Prompt hook] {prompt}",
        )

    async def _execute_http_hook(self, hook: HookConfig, context: dict) -> HookResult:
        """Execute an HTTP webhook hook."""
        url = hook.url
        if not url:
            return HookResult(success=False, error="No URL specified")

        try:
            import httpx
            timeout_sec = hook.timeout / 1000.0
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.post(
                    url,
                    json=context,
                    headers=hook.headers or {},
                )
                return HookResult(
                    success=resp.is_success,
                    output=resp.text[:1000],
                )
        except ImportError:
            return HookResult(success=False, error="httpx not installed")
        except Exception as e:
            return HookResult(success=False, error=str(e))

    async def trigger(
        self,
        event: str,
        tool_name: str | None = None,
        args: dict | None = None,
        context: dict | None = None,
    ) -> list[HookResult]:
        """Trigger all hooks for a given event.

        Args:
            event: The event name (PreToolUse, PostToolUse, PreReply, PostReply).
            tool_name: The tool name (for tool-related events).
            args: The tool arguments (for tool-related events).
            context: Additional context data passed to hooks.

        Returns:
            List of hook results.
        """
        ctx = dict(context or {})
        ctx["event"] = event
        if tool_name:
            ctx["tool_name"] = tool_name
        if args:
            ctx["args"] = args

        results = []
        to_remove = []

        for i, hook in enumerate(self._hooks):
            if hook.event != event:
                continue

            if not self._match_condition(hook, tool_name, args):
                continue

            # Skip already executed once-hooks
            if hook.once and id(hook) in self._once_executed:
                continue

            # Execute based on type
            if hook.async_execution:
                # Fire and forget
                asyncio.create_task(self._execute_single(hook, ctx))
                results.append(HookResult(success=True, output="(async)"))
            else:
                result = await self._execute_single(hook, ctx)
                results.append(result)

            # Mark once-hooks
            if hook.once:
                self._once_executed.add(id(hook))
                to_remove.append(i)

        # Remove once-hooks (reverse order to keep indices valid)
        for i in reversed(to_remove):
            self._hooks.pop(i)

        return results

    async def _execute_single(self, hook: HookConfig, ctx: dict) -> HookResult:
        """Execute a single hook."""
        try:
            if hook.type == "command":
                return await self._execute_command_hook(hook, ctx)
            elif hook.type == "prompt":
                return await self._execute_prompt_hook(hook, ctx)
            elif hook.type == "http":
                return await self._execute_http_hook(hook, ctx)
            else:
                return HookResult(success=False, error=f"Unknown hook type: {hook.type}")
        except Exception as e:
            return HookResult(success=False, error=str(e))

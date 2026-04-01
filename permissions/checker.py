# -*- coding: utf-8 -*-
"""Permission checker - Toolkit middleware for tool call authorization.

Implements R35-R37 from the plan.
"""
import fnmatch
from typing import Any, AsyncGenerator, Callable, Awaitable

from agentscope.message import ToolUseBlock, TextBlock
from agentscope.tool import ToolResponse

from ..config.schema import PermissionsConfig, PermissionRule
from .rules import PermRule, parse_rule, match_rule


class PermissionChecker:
    """Checks tool calls against permission rules.

    Supports three modes:
    - default: Ask user for each unrecognized tool call
    - acceptEdits: Auto-approve file operations
    - bypassPermissions: Auto-approve everything
    """

    def __init__(
        self,
        config: PermissionsConfig,
        ask_callback: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._config = config
        self._ask_callback = ask_callback

        # Parse allow/deny rules
        self._allow_rules: list[PermRule] = []
        for rule in config.allow_rules:
            parsed = PermRule(tool_name=rule.tool, pattern=rule.pattern)
            self._allow_rules.append(parsed)

        self._deny_rules: list[PermRule] = []
        for rule in config.deny_rules:
            parsed = PermRule(tool_name=rule.tool, pattern=rule.pattern)
            self._deny_rules.append(parsed)

        # Session-level "always allow" additions
        self._session_allow: list[PermRule] = []

        # Sensitive file patterns
        self._sensitive_patterns = config.sensitive_files

    def _is_sensitive_file(self, path: str) -> bool:
        """Check if a file path matches sensitive file patterns."""
        import os
        basename = os.path.basename(path)
        return any(
            fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(path, pat)
            for pat in self._sensitive_patterns
        )

    def _get_args_str(self, tool_call: ToolUseBlock) -> str:
        """Extract a string representation of tool arguments for matching."""
        args = tool_call.input if hasattr(tool_call, 'input') else {}
        if isinstance(args, dict):
            # For Bash, use command; for File ops, use file_path
            if "command" in args:
                return str(args["command"])
            if "file_path" in args:
                return str(args["file_path"])
            return str(args)
        return str(args)

    def check(self, tool_name: str, args_str: str) -> str:
        """Check permission for a tool call.

        Returns:
            'allow' - proceed with execution
            'deny' - block the call
            'ask' - need to ask user
        """
        mode = self._config.mode

        # Deny rules are ALWAYS enforced, even in bypass mode
        for rule in self._deny_rules:
            if match_rule(rule, tool_name, args_str):
                return "deny"

        # Check sensitive files (always enforced)
        if tool_name in ("FileRead", "FileWrite", "FileEdit"):
            if self._is_sensitive_file(args_str):
                return "deny"

        # bypassPermissions: allow everything else
        if mode == "bypassPermissions":
            return "allow"

        # Check allow rules
        all_allow = self._allow_rules + self._session_allow
        for rule in all_allow:
            if match_rule(rule, tool_name, args_str):
                return "allow"

        # acceptEdits: auto-approve file operations
        if mode == "acceptEdits" and tool_name in (
            "FileRead", "FileWrite", "FileEdit", "GlobSearch", "GrepSearch",
        ):
            return "allow"

        # Read-only tools are always allowed
        if tool_name in ("FileRead", "GlobSearch", "GrepSearch"):
            return "allow"

        return "ask"

    def add_session_rule(self, tool_name: str, pattern: str = "*") -> None:
        """Add a session-level allow rule (from 'Always allow' choice)."""
        self._session_allow.append(PermRule(tool_name=tool_name, pattern=pattern))

    def create_middleware(self):
        """Create a Toolkit middleware function for permission checking.

        Returns an async generator middleware compatible with Toolkit._apply_middlewares.
        """
        checker = self

        async def permission_middleware(
            kwargs: dict[str, Any],
            next_handler: Callable,
        ) -> AsyncGenerator[ToolResponse, None]:
            """Middleware that checks permissions before tool execution."""
            tool_call = kwargs.get("tool_call")
            if tool_call is None:
                async for chunk in await next_handler(**kwargs):
                    yield chunk
                return

            tool_name = tool_call.name if hasattr(tool_call, 'name') else "unknown"
            args_str = checker._get_args_str(tool_call)
            decision = checker.check(tool_name, args_str)

            if decision == "deny":
                yield ToolResponse(
                    content=[TextBlock(
                        text=f"Permission denied: {tool_name} is blocked by security rules.",
                    )],
                )
                return

            if decision == "ask" and checker._ask_callback:
                response = await checker._ask_callback(
                    f"Allow {tool_name}({args_str[:100]})? [Y]es/[N]o/[A]lways"
                )
                response = response.strip().lower()
                if response in ("n", "no"):
                    yield ToolResponse(
                        content=[TextBlock(text=f"Permission denied by user: {tool_name}")],
                    )
                    return
                if response in ("a", "always"):
                    checker.add_session_rule(tool_name, "*")

            # Proceed with tool execution
            async for chunk in await next_handler(**kwargs):
                yield chunk

        return permission_middleware

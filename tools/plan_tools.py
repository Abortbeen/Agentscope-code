# -*- coding: utf-8 -*-
"""Plan mode tools - enter/exit plan mode with read-only restriction.

Implements R28-R29 from the plan.
"""
import os
from datetime import datetime
from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

# Plan mode state
_plan_mode = False

# Read-only tools allowed in plan mode
_READONLY_TOOLS = {"FileRead", "GlobSearch", "GrepSearch", "AskUser", "WebFetch", "WebSearch"}


def is_plan_mode() -> bool:
    """Check if plan mode is active."""
    return _plan_mode


def get_readonly_tools() -> set[str]:
    """Get the set of tools allowed in plan mode."""
    return _READONLY_TOOLS


async def enter_plan_mode() -> ToolResponse:
    """Enter plan mode. Restricts tools to read-only operations.

    In plan mode, only FileRead, GlobSearch, GrepSearch, AskUser,
    WebFetch, and WebSearch are available.

    Returns:
        ToolResponse confirming plan mode entry.
    """
    global _plan_mode
    _plan_mode = True
    return ToolResponse(
        content=[TextBlock(
            text="Plan mode activated. Only read-only tools are available.\n"
            f"Allowed: {', '.join(sorted(_READONLY_TOOLS))}\n"
            "Use ExitPlanMode to save the plan and restore all tools.",
        )],
    )


async def exit_plan_mode(
    plan_content: str,
) -> ToolResponse:
    """Exit plan mode and save the plan.

    Args:
        plan_content: The plan content to save.

    Returns:
        ToolResponse confirming plan save and mode exit.
    """
    global _plan_mode

    if not _plan_mode:
        return ToolResponse(
            content=[TextBlock(text="Not currently in plan mode.")],
        )

    # Save plan to .agent/plans/
    plans_dir = Path.cwd() / ".agent" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_file = plans_dir / f"{timestamp}-plan.md"

    try:
        plan_file.write_text(plan_content, encoding="utf-8")
        saved_msg = f"Plan saved to {plan_file}"
    except OSError as e:
        saved_msg = f"Warning: Could not save plan: {e}"

    _plan_mode = False

    return ToolResponse(
        content=[TextBlock(
            text=f"Plan mode deactivated. All tools restored.\n{saved_msg}",
        )],
    )

# -*- coding: utf-8 -*-
"""AskUser tool - Allows the agent to ask the user a question."""
import asyncio
from typing import Callable, Awaitable

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

# Global callback that the REPL sets
_ask_user_callback: Callable[[str], Awaitable[str]] | None = None


def set_ask_user_callback(callback: Callable[[str], Awaitable[str]]) -> None:
    """Set the callback function for asking the user. Called by the REPL."""
    global _ask_user_callback
    _ask_user_callback = callback


async def ask_user(
    question: str,
) -> ToolResponse:
    """Ask the user a question and wait for their response.

    Use this when you need clarification or confirmation from the user.

    Args:
        question: The question to ask the user.

    Returns:
        ToolResponse with the user's answer.
    """
    if _ask_user_callback is None:
        return ToolResponse(
            content=[TextBlock(
                text="Error: No user interaction available (non-interactive mode).",
            )],
        )

    try:
        answer = await _ask_user_callback(question)
        return ToolResponse(
            content=[TextBlock(text=f"User's response: {answer}")],
        )
    except Exception as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error getting user input: {e}")],
        )

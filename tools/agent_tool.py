# -*- coding: utf-8 -*-
"""AgentTool - Spawn sub-agents for subtasks.

Implements R11-R12 from the plan.
Sub-agents share the same Toolkit but run as independent ReActAgent instances.
"""
import asyncio
from typing import Any

from agentscope.message import Msg, TextBlock
from agentscope.tool import ToolResponse

from ..agent.agent_loader import AgentDefinitionLoader


# Registry of active sub-agents
_active_agents: dict[str, Any] = {}

# Reference to parent agent's toolkit (set during init)
_parent_toolkit = None
_parent_model_config = None


def set_parent_context(toolkit, model_config) -> None:
    """Set the parent agent's toolkit and model config for sub-agent creation.

    Called by the REPL during initialization.
    """
    global _parent_toolkit, _parent_model_config
    _parent_toolkit = toolkit
    _parent_model_config = model_config


async def spawn_agent(
    prompt: str,
    agent_type: str | None = None,
    description: str = "",
) -> ToolResponse:
    """Spawn a sub-agent to handle a subtask.

    The sub-agent runs asynchronously using the same toolkit as the parent.
    It receives the prompt as its task and returns the final result.

    Args:
        prompt: The task description for the sub-agent.
        agent_type: Optional agent type (maps to .agent/agents/ definitions).
        description: Short description of what the agent will do.

    Returns:
        ToolResponse with the sub-agent's result.
    """
    if _parent_toolkit is None or _parent_model_config is None:
        return ToolResponse(
            content=[TextBlock(
                text="Error: Agent spawning not initialized. "
                "Parent toolkit and model config must be set first.",
            )],
        )

    try:
        from ..agent.coding_agent import CodingAgent

        # Check for custom agent definition (bundled + user + project)
        extra_prompt = ""
        if agent_type:
            loader = AgentDefinitionLoader()
            defn = loader.get_definition(agent_type)
            if defn:
                extra_prompt = f"\n\nAgent Role: {defn.description}\n{defn.system_prompt}"
            else:
                extra_prompt = f"\n\nAgent type: {agent_type}"

        # Create sub-agent with shared toolkit
        import shortuuid
        agent_id = shortuuid.uuid()[:8]
        agent_name = f"SubAgent-{agent_id}"

        sub_agent = CodingAgent(
            model_config=_parent_model_config,
            toolkit=_parent_toolkit,
            max_iters=15,  # Lower limit for sub-agents
            name=agent_name,
        )

        # Track active agent
        _active_agents[agent_name] = sub_agent

        # Run sub-agent with timeout
        full_prompt = prompt
        if extra_prompt:
            full_prompt = prompt + extra_prompt

        try:
            async with asyncio.timeout(300):  # 5 minute timeout
                result_msg = await sub_agent.reply(full_prompt)
        except asyncio.TimeoutError:
            return ToolResponse(
                content=[TextBlock(
                    text=f"[SubAgent {agent_name}] Timed out after 5 minutes.\n"
                    f"Task: {description or prompt[:100]}",
                )],
                metadata={"agent_id": agent_name, "status": "timeout"},
            )
        finally:
            _active_agents.pop(agent_name, None)

        # Extract final response
        if result_msg:
            if isinstance(result_msg, Msg):
                content = result_msg.content
                if isinstance(content, str):
                    result_text = content
                elif isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
                    result_text = "\n".join(text_parts)
                else:
                    result_text = str(content)
            else:
                result_text = str(result_msg)
        else:
            result_text = "(No response from sub-agent)"

        return ToolResponse(
            content=[TextBlock(
                text=f"[SubAgent {agent_name}] Result:\n\n{result_text}",
            )],
            metadata={"agent_id": agent_name, "status": "completed"},
        )

    except Exception as e:
        return ToolResponse(
            content=[TextBlock(
                text=f"Error spawning sub-agent: {e}",
            )],
            metadata={"status": "error"},
        )


async def send_message(
    to: str,
    message: str,
) -> ToolResponse:
    """Send a message to another active agent.

    Args:
        to: The name or ID of the target agent.
        message: The message content.

    Returns:
        ToolResponse confirming delivery or error.
    """
    target = _active_agents.get(to)
    if target is None:
        # Try partial match
        for name, agent in _active_agents.items():
            if to in name:
                target = agent
                to = name
                break

    if target is None:
        active = list(_active_agents.keys())
        if active:
            return ToolResponse(
                content=[TextBlock(
                    text=f"Error: Agent '{to}' not found. "
                    f"Active agents: {', '.join(active)}",
                )],
            )
        return ToolResponse(
            content=[TextBlock(
                text=f"Error: Agent '{to}' not found. No active sub-agents.",
            )],
        )

    # Send message by injecting into sub-agent's reply
    try:
        result_msg = await target.reply(message)

        if result_msg:
            if isinstance(result_msg, Msg) and isinstance(result_msg.content, str):
                reply_text = result_msg.content
            else:
                reply_text = str(result_msg)
        else:
            reply_text = "(No response)"

        return ToolResponse(
            content=[TextBlock(
                text=f"[{to}] replied:\n{reply_text}",
            )],
        )
    except Exception as e:
        return ToolResponse(
            content=[TextBlock(text=f"Error sending message to {to}: {e}")],
        )

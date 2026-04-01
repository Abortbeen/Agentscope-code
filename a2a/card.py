# -*- coding: utf-8 -*-
"""Agent Card builder for A2A protocol.

An Agent Card is a JSON document that describes an agent's capabilities,
following Google's A2A (Agent-to-Agent) protocol specification.
"""
from typing import Any

from ..config.schema import A2AConfig


def build_agent_card(
    config: A2AConfig,
    tools: list[str] | None = None,
) -> dict[str, Any]:
    """Build an A2A-compliant Agent Card.

    The Agent Card is served at /.well-known/agent.json and allows
    other agents to discover this agent's capabilities.

    Args:
        config: A2A configuration.
        tools: List of available tool names.

    Returns:
        Agent Card as a dict (JSON-serializable).
    """
    base_url = f"http://{config.host}:{config.port}"

    # Build skills list from config + tool names
    skills = []
    for skill_name in config.skills:
        skills.append({
            "id": skill_name,
            "name": skill_name.replace("_", " ").title(),
            "description": f"Ability to perform {skill_name.replace('_', ' ')}",
            "tags": [skill_name],
        })

    # Add tool-based skills
    if tools:
        for tool_name in tools:
            skills.append({
                "id": f"tool_{tool_name.lower()}",
                "name": f"Tool: {tool_name}",
                "description": f"Execute {tool_name} tool",
                "tags": ["tool", tool_name.lower()],
            })

    card = {
        "name": config.agent_name,
        "description": config.agent_description,
        "url": base_url,
        "version": config.agent_version,
        "protocol_version": "0.2.1",
        "capabilities": {
            "streaming": True,
            "push_notifications": False,
            "state_transition_history": True,
        },
        "authentication": {
            "schemes": [],  # No auth by default
        },
        "default_input_modes": ["text/plain"],
        "default_output_modes": ["text/plain"],
        "skills": skills,
        "provider": {
            "organization": "CodeAgent",
            "url": "https://github.com/codeagent",
        },
    }

    return card


def save_agent_card(card: dict[str, Any], path: str) -> None:
    """Save Agent Card to a JSON file.

    Args:
        card: Agent Card dict.
        path: File path to save to.
    """
    import json
    import os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2, ensure_ascii=False)

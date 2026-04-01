# -*- coding: utf-8 -*-
"""Skill invocation tool - invoke a registered skill by name.

Implements R22 from the plan.
"""
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from .registry import SkillRegistry

# Module-level registry instance; should be set by the agent on startup.
_registry: SkillRegistry | None = None


def set_registry(registry: SkillRegistry) -> None:
    """Set the global skill registry for the skill tool.

    Args:
        registry: The SkillRegistry instance to use.
    """
    global _registry
    _registry = registry


async def invoke_skill(
    name: str,
    args: str = "",
) -> ToolResponse:
    """Invoke a registered skill by name.

    Looks up the skill in the registry and returns its prompt content,
    which the agent can then follow to execute the skill.

    Args:
        name: Name of the skill to invoke.
        args: Optional arguments string to pass to the skill.

    Returns:
        ToolResponse with the skill's prompt content or an error.
    """
    if _registry is None:
        return ToolResponse(
            content=[TextBlock(
                text="Error: Skill registry not initialized. "
                "Call set_registry() before invoking skills.",
            )],
        )

    skill = _registry.get(name)
    if skill is None:
        available = _registry.list_skills()
        if available:
            names = ", ".join(s.name for s in available)
            return ToolResponse(
                content=[TextBlock(
                    text=f"Error: Skill '{name}' not found. Available skills: {names}",
                )],
            )
        return ToolResponse(
            content=[TextBlock(text=f"Error: Skill '{name}' not found. No skills registered.")],
        )

    prompt = skill.prompt
    if not prompt:
        return ToolResponse(
            content=[TextBlock(
                text=f"Error: Skill '{name}' has no prompt content.",
            )],
        )

    # Prepend args context if provided
    header = f"Invoking skill: {name}"
    if args:
        header += f"\nArguments: {args}"
    if skill.description:
        header += f"\nDescription: {skill.description}"

    return ToolResponse(
        content=[TextBlock(text=f"{header}\n\n---\n\n{prompt}")],
    )

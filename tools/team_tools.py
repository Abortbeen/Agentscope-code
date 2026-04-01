# -*- coding: utf-8 -*-
"""Team tools - create, manage, and coordinate multi-agent teams.

Implements R15 from the plan.
Uses AgentScope MsgHub for real multi-agent broadcast communication.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Any

from agentscope.agent import ReActAgent
from agentscope.message import Msg, TextBlock
from agentscope.pipeline import MsgHub
from agentscope.tool import ToolResponse

from ..agent.coding_agent import CodingAgent

# Module-level references (set by REPL during init)
_parent_toolkit = None
_parent_model_config = None

# Active teams
_teams: dict[str, "Team"] = {}


@dataclass
class Team:
    """Represents an active agent team with MsgHub communication."""
    name: str
    description: str = ""
    members: dict[str, CodingAgent] = field(default_factory=dict)
    hub: MsgHub | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def set_team_context(toolkit, model_config) -> None:
    """Set the parent context for team member creation."""
    global _parent_toolkit, _parent_model_config
    _parent_toolkit = toolkit
    _parent_model_config = model_config


async def team_create(
    name: str,
    description: str = "",
    members: list[str] | None = None,
) -> ToolResponse:
    """Create a new agent team with MsgHub communication.

    Team members are CodingAgent instances that share a Toolkit and
    communicate via AgentScope MsgHub (broadcast messaging).

    Args:
        name: Unique name for the team.
        description: Purpose of the team.
        members: Optional list of member names to pre-create.
            Each becomes a CodingAgent with the shared toolkit.

    Returns:
        ToolResponse with creation result.
    """
    if not name or not name.strip():
        return ToolResponse(
            content=[TextBlock(text="Error: Team name cannot be empty.")],
        )

    if name in _teams:
        return ToolResponse(
            content=[TextBlock(text=f"Error: Team '{name}' already exists.")],
        )

    if _parent_toolkit is None or _parent_model_config is None:
        return ToolResponse(
            content=[TextBlock(
                text="Error: Team context not initialized. "
                "Cannot create team members.",
            )],
        )

    team = Team(name=name, description=description)

    # Create member agents
    member_names = members or []
    member_agents = []
    for member_name in member_names:
        agent = CodingAgent(
            model_config=_parent_model_config,
            toolkit=_parent_toolkit,
            max_iters=10,
            name=member_name,
        )
        team.members[member_name] = agent
        member_agents.append(agent.agent)  # ReActAgent instances for MsgHub

    # Create MsgHub for broadcast communication
    if member_agents:
        announcement = Msg(
            name="system",
            content=f"Team '{name}' created. Purpose: {description}. "
            f"Members: {', '.join(member_names)}. "
            "Collaborate to complete tasks on the shared task board.",
            role="system",
        )
        team.hub = MsgHub(
            participants=member_agents,
            announcement=announcement,
            enable_auto_broadcast=True,
            name=name,
        )

    _teams[name] = team

    return ToolResponse(
        content=[TextBlock(
            text=f"Created team '{name}' with {len(member_agents)} members.\n"
            f"Description: {description}\n"
            f"Members: {', '.join(member_names) if member_names else '(none yet)'}\n"
            "Use TeamAddMember to add more, or TeamRun to assign tasks.",
        )],
        metadata={"team": name, "members": member_names},
    )


async def team_add_member(
    team_name: str,
    member_name: str,
    role: str = "",
) -> ToolResponse:
    """Add a new member to an existing team.

    Args:
        team_name: Name of the team.
        member_name: Name for the new member agent.
        role: Optional role description for the agent.

    Returns:
        ToolResponse confirming addition.
    """
    team = _teams.get(team_name)
    if not team:
        return ToolResponse(
            content=[TextBlock(text=f"Error: Team '{team_name}' not found.")],
        )

    if member_name in team.members:
        return ToolResponse(
            content=[TextBlock(text=f"Error: '{member_name}' already in team.")],
        )

    if _parent_toolkit is None or _parent_model_config is None:
        return ToolResponse(
            content=[TextBlock(text="Error: Team context not initialized.")],
        )

    agent = CodingAgent(
        model_config=_parent_model_config,
        toolkit=_parent_toolkit,
        max_iters=10,
        name=member_name,
    )
    team.members[member_name] = agent

    # Add to MsgHub
    if team.hub:
        team.hub.add(agent.agent)
    else:
        # Create hub with first member
        team.hub = MsgHub(
            participants=[agent.agent],
            enable_auto_broadcast=True,
            name=team_name,
        )

    return ToolResponse(
        content=[TextBlock(
            text=f"Added '{member_name}' to team '{team_name}'."
            + (f" Role: {role}" if role else ""),
        )],
    )


async def team_run(
    team_name: str,
    task: str,
    parallel: bool = True,
) -> ToolResponse:
    """Assign a task to a team. Members work on it via MsgHub.

    In parallel mode, all members receive the task simultaneously.
    In sequential mode, members take turns responding.

    Args:
        team_name: Name of the team.
        task: The task description/prompt.
        parallel: If True, all members work simultaneously.

    Returns:
        ToolResponse with combined results from all members.
    """
    team = _teams.get(team_name)
    if not team:
        return ToolResponse(
            content=[TextBlock(text=f"Error: Team '{team_name}' not found.")],
        )

    if not team.members:
        return ToolResponse(
            content=[TextBlock(text=f"Error: Team '{team_name}' has no members.")],
        )

    results = []

    if parallel:
        # All members work on the task simultaneously
        async def _run_member(name: str, agent: CodingAgent):
            try:
                result = await asyncio.wait_for(
                    agent.reply(task),
                    timeout=300,
                )
                if isinstance(result, Msg):
                    content = result.content
                    if isinstance(content, str):
                        return name, content
                    elif isinstance(content, list):
                        texts = []
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "text":
                                texts.append(b["text"])
                        return name, "\n".join(texts)
                return name, str(result)
            except asyncio.TimeoutError:
                return name, "(timed out)"
            except Exception as e:
                return name, f"(error: {e})"

        tasks = [
            _run_member(name, agent)
            for name, agent in team.members.items()
        ]
        results = await asyncio.gather(*tasks)
    else:
        # Sequential: each member builds on previous responses
        if team.hub:
            async with team.hub:
                for name, agent in team.members.items():
                    try:
                        result = await asyncio.wait_for(
                            agent.reply(task),
                            timeout=300,
                        )
                        if isinstance(result, Msg):
                            content = result.content
                            text = content if isinstance(content, str) else str(content)
                        else:
                            text = str(result)
                        results.append((name, text))
                    except Exception as e:
                        results.append((name, f"(error: {e})"))

    # Format combined output
    output_lines = [f"Team '{team_name}' results ({len(results)} members):\n"]
    for name, text in results:
        output_lines.append(f"--- {name} ---")
        output_lines.append(text[:2000])
        output_lines.append("")

    return ToolResponse(
        content=[TextBlock(text="\n".join(output_lines))],
        metadata={"team": team_name, "members": len(results)},
    )


async def team_delete(name: str) -> ToolResponse:
    """Delete a team and clean up resources.

    Args:
        name: Name of the team to delete.

    Returns:
        ToolResponse confirming deletion.
    """
    team = _teams.get(name)
    if not team:
        return ToolResponse(
            content=[TextBlock(text=f"Error: Team '{name}' not found.")],
        )

    # Clean up MsgHub
    team.hub = None
    team.members.clear()
    del _teams[name]

    return ToolResponse(
        content=[TextBlock(text=f"Deleted team '{name}'.")],
    )


async def team_list() -> ToolResponse:
    """List all active teams and their members.

    Returns:
        ToolResponse with team summaries.
    """
    if not _teams:
        return ToolResponse(
            content=[TextBlock(text="No active teams.")],
        )

    lines = [f"Active teams ({len(_teams)}):"]
    for team in _teams.values():
        desc = f" — {team.description}" if team.description else ""
        members = ", ".join(team.members.keys()) if team.members else "(no members)"
        has_hub = "MsgHub active" if team.hub else "no hub"
        lines.append(f"  📋 **{team.name}**{desc}")
        lines.append(f"     Members: {members}")
        lines.append(f"     Status: {has_hub}")

    return ToolResponse(
        content=[TextBlock(text="\n".join(lines))],
    )

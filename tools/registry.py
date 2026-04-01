# -*- coding: utf-8 -*-
"""Tool registry - registers all coding tools into an AgentScope Toolkit."""
from agentscope.tool import Toolkit

from .bash_tool import bash_execute
from .file_tools import file_read, file_write, file_edit
from .glob_tool import glob_search
from .grep_tool import grep_search
from .web_tools import web_fetch, web_search
from .ask_user_tool import ask_user
from .agent_tool import spawn_agent, send_message
from .plan_tools import enter_plan_mode, exit_plan_mode
from .task_tools import task_create, task_update, task_list
from .team_tools import team_create, team_add_member, team_run, team_delete, team_list


def register_all_tools(toolkit: Toolkit | None = None) -> Toolkit:
    """Register all coding tools into a Toolkit instance.

    All tools are registered in the "basic" group so they are always
    available in the agent's JSON schema.

    Args:
        toolkit: Existing Toolkit to add tools to. Creates new one if None.

    Returns:
        The Toolkit with all tools registered.
    """
    if toolkit is None:
        toolkit = Toolkit()

    # All tools in "basic" group (always active)
    _all_tools: list[tuple] = [
        # Core tools
        (bash_execute, "Bash", "Execute a shell command and return its output."),
        (file_read, "FileRead", "Read a file's contents with line numbers."),
        (file_write, "FileWrite", "Write content to a file (creates parent dirs)."),
        (file_edit, "FileEdit", "Perform exact string replacement in a file."),
        (glob_search, "GlobSearch", "Search for files matching a glob pattern."),
        (grep_search, "GrepSearch", "Search file contents using regex patterns."),
        # Web tools
        (web_fetch, "WebFetch", "Fetch a web page and return its content."),
        (web_search, "WebSearch", "Search the web for information."),
        # Interaction
        (ask_user, "AskUser", "Ask the user a question and wait for their response."),
        # Agent coordination
        (spawn_agent, "SpawnAgent", "Spawn a sub-agent to handle a subtask."),
        (send_message, "SendMessage", "Send a message to another agent."),
        # Task board
        (task_create, "TaskCreate", "Create a new task on the task board."),
        (task_update, "TaskUpdate", "Update an existing task's status."),
        (task_list, "TaskList", "List all tasks on the task board."),
        # Plan mode
        (enter_plan_mode, "EnterPlanMode", "Enter plan mode (read-only tools only)."),
        (exit_plan_mode, "ExitPlanMode", "Exit plan mode and save the plan."),
        # Team coordination
        (team_create, "TeamCreate", "Create a multi-agent team with MsgHub communication."),
        (team_add_member, "TeamAddMember", "Add a member agent to an existing team."),
        (team_run, "TeamRun", "Assign a task to a team (parallel or sequential)."),
        (team_delete, "TeamDelete", "Delete a team and clean up resources."),
        (team_list, "TeamList", "List all active teams and their members."),
    ]

    for func, name, desc in _all_tools:
        toolkit.register_tool_function(
            tool_func=func,
            func_name=name,
            func_description=desc,
            group_name="basic",
            namesake_strategy="skip",
        )

    # Git tools (registered if module available)
    try:
        from .git_tools import (
            git_status, git_diff, git_log, git_commit,
            git_worktree_create, git_worktree_remove,
        )
        _git_tools = [
            (git_status, "GitStatus", "Show current git repository status."),
            (git_diff, "GitDiff", "Show git diff for working directory or staged changes."),
            (git_log, "GitLog", "Show recent git commit history."),
            (git_commit, "GitCommit", "Create a git commit with attribution."),
            (git_worktree_create, "GitWorktreeCreate", "Create a git worktree for isolated work."),
            (git_worktree_remove, "GitWorktreeRemove", "Remove a git worktree."),
        ]

        for func, name, desc in _git_tools:
            toolkit.register_tool_function(
                tool_func=func,
                func_name=name,
                func_description=desc,
                group_name="basic",
                namesake_strategy="skip",
            )
    except ImportError:
        pass  # git_tools not yet available

    # Notebook tool (registered if nbformat available)
    try:
        from .notebook_tool import notebook_edit
        toolkit.register_tool_function(
            tool_func=notebook_edit,
            func_name="NotebookEdit",
            func_description="Edit a Jupyter notebook cell.",
            group_name="basic",
            namesake_strategy="skip",
        )
    except ImportError:
        pass  # nbformat not installed

    return toolkit

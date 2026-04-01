# -*- coding: utf-8 -*-
"""Tool functions for CodeAgent.

All tools are registered via AgentScope's Toolkit.register_tool_function().
"""
from .bash_tool import bash_execute
from .file_tools import file_read, file_write, file_edit
from .glob_tool import glob_search
from .grep_tool import grep_search
from .web_tools import web_fetch, web_search
from .ask_user_tool import ask_user
from .agent_tool import spawn_agent, send_message
from .plan_tools import enter_plan_mode, exit_plan_mode
from .task_tools import task_create, task_update, task_list
from .registry import register_all_tools

__all__ = [
    "bash_execute",
    "file_read",
    "file_write",
    "file_edit",
    "glob_search",
    "grep_search",
    "web_fetch",
    "web_search",
    "ask_user",
    "spawn_agent",
    "send_message",
    "enter_plan_mode",
    "exit_plan_mode",
    "task_create",
    "task_update",
    "task_list",
    "register_all_tools",
]

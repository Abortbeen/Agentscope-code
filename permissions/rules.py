# -*- coding: utf-8 -*-
"""Permission rule parsing and matching using fnmatch.

Rule format: "ToolName(pattern)" e.g. "Bash(git *)", "FileRead(*.py)"
"""
import fnmatch
import re
from dataclasses import dataclass

_RULE_RE = re.compile(r"^(\w+)\((.+)\)$")


@dataclass
class PermRule:
    """A parsed permission rule."""
    tool_name: str
    pattern: str


def parse_rule(rule_str: str) -> PermRule | None:
    """Parse a rule string like 'Bash(git *)' into a PermRule.

    Args:
        rule_str: The rule string.

    Returns:
        PermRule or None if parsing fails.
    """
    match = _RULE_RE.match(rule_str.strip())
    if match:
        return PermRule(tool_name=match.group(1), pattern=match.group(2))

    # Simple form: just tool name means allow all
    name = rule_str.strip()
    if name.isidentifier():
        return PermRule(tool_name=name, pattern="*")

    return None


def match_rule(rule: PermRule, tool_name: str, args_str: str) -> bool:
    """Check if a tool call matches a permission rule.

    Args:
        rule: The permission rule.
        tool_name: The tool being called.
        args_str: String representation of the tool arguments.

    Returns:
        True if the rule matches.
    """
    if rule.tool_name != tool_name and rule.tool_name != "*":
        return False
    return fnmatch.fnmatch(args_str, rule.pattern)

# -*- coding: utf-8 -*-
"""Configuration schema definitions using Pydantic models.

Field naming follows Claude Code settings.json conventions for migration compatibility.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Model provider configuration."""

    provider: str = Field(
        default="openai",
        description="Model provider: openai, anthropic, dashscope, gemini, ollama",
    )
    model_name: str = Field(
        default="gpt-4o",
        description="Model name to use",
    )
    api_key: str | None = Field(
        default=None,
        description="API key (prefer env var over config file)",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom API base URL",
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=8192, gt=0)
    stream: bool = Field(default=True)


class PermissionRule(BaseModel):
    """A single permission rule, e.g. Bash(git *)."""

    tool: str = Field(description="Tool name, e.g. 'Bash'")
    pattern: str = Field(
        default="*",
        description="Argument pattern (fnmatch), e.g. 'git *'",
    )


class PermissionsConfig(BaseModel):
    """Permission control configuration."""

    mode: str = Field(
        default="default",
        description="Permission mode: default, acceptEdits, bypassPermissions",
    )
    allow_rules: list[PermissionRule] = Field(
        default_factory=list,
        description="Whitelist rules for auto-approval",
    )
    deny_rules: list[PermissionRule] = Field(
        default_factory=list,
        description="Blacklist rules that always block",
    )
    sensitive_files: list[str] = Field(
        default_factory=lambda: [
            ".env", ".env.*", "*.pem", "*.key",
            "credentials*", "secret*", "*password*",
        ],
        description="Glob patterns for sensitive files",
    )


class HookCondition(BaseModel):
    """Condition for hook matching."""

    tool_name: str | None = Field(default=None)
    pattern: str | None = Field(default=None)


class HookConfig(BaseModel):
    """Hook configuration entry."""

    event: str = Field(
        description="Hook event: PreToolUse, PostToolUse, PreReply, PostReply",
    )
    type: Literal["command", "prompt", "http"] = Field(
        description="Hook type",
    )

    # For command hooks
    command: str | None = Field(default=None)

    # For prompt hooks
    prompt: str | None = Field(default=None)
    model: str | None = Field(default=None)

    # For http hooks
    url: str | None = Field(default=None)
    headers: dict[str, str] | None = Field(default=None)

    # Shared options
    condition: HookCondition | None = Field(
        default=None,
        alias="if",
        description="Condition filter for the hook",
    )
    timeout: int = Field(default=10000, description="Timeout in ms")
    async_execution: bool = Field(
        default=False,
        alias="async",
        description="Run in background",
    )
    once: bool = Field(default=False, description="Run only once then remove")

    model_config = {"populate_by_name": True}


class SkillsConfig(BaseModel):
    """Skills system configuration."""

    extra_dirs: list[str] = Field(
        default_factory=list,
        description="Additional directories to scan for skills",
    )
    disabled: list[str] = Field(
        default_factory=list,
        description="List of disabled skill names",
    )


class SessionConfig(BaseModel):
    """Session management configuration."""

    storage_dir: str | None = Field(
        default=None,
        description="Custom session storage directory",
    )
    max_sessions: int = Field(
        default=50,
        description="Maximum number of saved sessions",
    )


class MemoryConfig(BaseModel):
    """Memory configuration."""

    memory_file: str = Field(
        default="AGENT.md",
        description="Project memory filename (also checks CLAUDE.md as fallback)",
    )
    compression_threshold: int = Field(
        default=100000,
        description="Token threshold to trigger memory compression",
    )
    keep_recent: int = Field(
        default=3,
        description="Number of recent messages to keep uncompressed",
    )


class UIConfig(BaseModel):
    """UI configuration."""

    theme: str = Field(default="monokai", description="Syntax highlight theme")
    show_tokens: bool = Field(default=True, description="Show token counter")
    show_cost: bool = Field(default=True, description="Show cost estimate")
    markdown_output: bool = Field(default=True, description="Render markdown")


class StudioConfig(BaseModel):
    """AgentScope Studio integration configuration."""

    enabled: bool = Field(default=False, description="Enable Studio connection")
    url: str | None = Field(
        default=None,
        description="Studio URL (e.g., http://localhost:7860)",
    )
    auto_launch: bool = Field(
        default=False,
        description="Auto-launch Studio if not running",
    )
    port: int = Field(default=7860, description="Port for auto-launched Studio")


class TracingConfig(BaseModel):
    """OpenTelemetry tracing configuration."""

    enabled: bool = Field(default=False, description="Enable tracing")
    url: str | None = Field(
        default=None,
        description="Tracing endpoint URL (OTLP). Falls back to Studio tracing if not set.",
    )


class A2AConfig(BaseModel):
    """A2A (Agent-to-Agent) protocol configuration."""

    enabled: bool = Field(default=False, description="Enable A2A server")
    host: str = Field(default="0.0.0.0", description="A2A server bind host")
    port: int = Field(default=7861, description="A2A server port")
    agent_name: str = Field(
        default="CodeAgent",
        description="Agent name published in Agent Card",
    )
    agent_description: str = Field(
        default="An AI coding agent built on AgentScope",
        description="Agent description in Agent Card",
    )
    agent_version: str = Field(default="0.1.0", description="Agent version")
    skills: list[str] = Field(
        default_factory=lambda: [
            "code_generation", "code_review", "debugging",
            "file_editing", "shell_commands", "web_search",
        ],
        description="Skills advertised in Agent Card",
    )

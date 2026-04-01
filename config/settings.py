# -*- coding: utf-8 -*-
"""Hierarchical configuration loading for CodeAgent.

Priority: CLI args > env vars > project .agent/settings.json > global settings > defaults
"""
import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .schema import (
    ModelConfig,
    PermissionsConfig,
    HookConfig,
    SkillsConfig,
    SessionConfig,
    MemoryConfig,
    UIConfig,
    StudioConfig,
    TracingConfig,
    A2AConfig,
)


class CodeAgentConfig(BaseModel):
    """Root configuration for CodeAgent."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    hooks: list[HookConfig] = Field(default_factory=list)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    studio: StudioConfig = Field(default_factory=StudioConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    a2a: A2AConfig = Field(default_factory=A2AConfig)

    # Extra settings from JSON that aren't modeled
    extra: dict[str, Any] = Field(default_factory=dict)


def _get_global_config_path() -> Path:
    """Get the global config file path."""
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg) / "codeagent" / "settings.json"


def _get_project_config_path() -> Path | None:
    """Find the project config by walking up from cwd."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".agent" / "settings.json"
        if candidate.exists():
            return candidate
        # Also check for .codeagent directory
        candidate2 = parent / ".codeagent" / "settings.json"
        if candidate2.exists():
            return candidate2
    return None


def _load_json_file(path: Path) -> dict[str, Any]:
    """Load a JSON file, returning empty dict on error."""
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except (json.JSONDecodeError, OSError) as e:
        import warnings
        warnings.warn(
            f"Failed to load config from {path}: {e}. Using defaults.",
            stacklevel=2,
        )
    return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base (override wins)."""
    result = base.copy()
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _env_overrides() -> dict[str, Any]:
    """Read config overrides from environment variables."""
    overrides: dict[str, Any] = {}

    # CODEAGENT_MODEL -> model.model_name
    if model := os.environ.get("CODEAGENT_MODEL"):
        overrides.setdefault("model", {})["model_name"] = model

    # CODEAGENT_PROVIDER -> model.provider
    if provider := os.environ.get("CODEAGENT_PROVIDER"):
        overrides.setdefault("model", {})["provider"] = provider

    # CODEAGENT_PERMISSION_MODE -> permissions.mode
    if mode := os.environ.get("CODEAGENT_PERMISSION_MODE"):
        overrides.setdefault("permissions", {})["mode"] = mode

    return overrides


def load_config() -> CodeAgentConfig:
    """Load and merge configuration from all sources.

    Priority (highest to lowest):
    1. Environment variables
    2. Project .agent/settings.json
    3. Global ~/.config/codeagent/settings.json
    4. Defaults
    """
    # Start with empty
    merged: dict[str, Any] = {}

    # Layer 1: Global config
    global_path = _get_global_config_path()
    global_data = _load_json_file(global_path)
    merged = _deep_merge(merged, global_data)

    # Layer 2: Project config
    project_path = _get_project_config_path()
    if project_path:
        project_data = _load_json_file(project_path)
        merged = _deep_merge(merged, project_data)

    # Layer 3: Environment variables
    env_data = _env_overrides()
    merged = _deep_merge(merged, env_data)

    # Parse into typed config
    try:
        config = CodeAgentConfig(**merged)
    except Exception:
        # If parsing fails, use defaults
        import warnings
        warnings.warn(
            "Config validation failed, using defaults.",
            stacklevel=2,
        )
        config = CodeAgentConfig()

    return config

# -*- coding: utf-8 -*-
"""The main CodingAgent built on AgentScope's ReActAgent.

This is the core agent that orchestrates tool usage, memory, and
the reasoning-acting loop for coding tasks.
"""
from typing import Literal

from agentscope.agent import ReActAgent
from agentscope.formatter import FormatterBase
from agentscope.memory import MemoryBase
from agentscope.model import ChatModelBase
from agentscope.tool import Toolkit

from .system_prompt import SystemPromptBuilder
from ..config.schema import ModelConfig, PermissionsConfig
from ..utils.git import GitInfo


# Model provider -> (ModelClass, FormatterClass) mapping
_PROVIDER_MAP: dict[str, tuple[str, str]] = {
    "openai": (
        "agentscope.model.OpenAIChatModel",
        "agentscope.formatter.OpenAIChatFormatter",
    ),
    "anthropic": (
        "agentscope.model.AnthropicChatModel",
        "agentscope.formatter.AnthropicChatFormatter",
    ),
    "dashscope": (
        "agentscope.model.DashScopeChatModel",
        "agentscope.formatter.DashScopeChatFormatter",
    ),
    "gemini": (
        "agentscope.model.GeminiChatModel",
        "agentscope.formatter.GeminiChatFormatter",
    ),
    "ollama": (
        "agentscope.model.OllamaChatModel",
        "agentscope.formatter.OllamaChatFormatter",
    ),
}


def _import_class(dotted_path: str):
    """Import a class from a dotted path string."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def create_model_and_formatter(
    config: ModelConfig,
) -> tuple[ChatModelBase, FormatterBase]:
    """Create model and formatter instances from config.

    Args:
        config: Model configuration.

    Returns:
        Tuple of (model, formatter).
    """
    provider = config.provider.lower()
    if provider not in _PROVIDER_MAP:
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            f"Supported: {list(_PROVIDER_MAP.keys())}"
        )

    model_cls_path, formatter_cls_path = _PROVIDER_MAP[provider]
    ModelCls = _import_class(model_cls_path)
    FormatterCls = _import_class(formatter_cls_path)

    # Build model kwargs
    model_kwargs: dict = {
        "model_name": config.model_name,
        "stream": config.stream,
    }

    # API key: config > environment variable > None
    import os
    _ENV_KEY_MAP = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "dashscope": "DASHSCOPE_API_KEY",
        "gemini": "GOOGLE_API_KEY",
    }
    api_key = config.api_key or os.environ.get(_ENV_KEY_MAP.get(provider, ""), None)
    if api_key:
        model_kwargs["api_key"] = api_key
    if config.max_tokens:
        model_kwargs["max_tokens"] = config.max_tokens

    # Handle base_url per provider
    # - OpenAI/Ollama/Gemini: direct `base_url` kwarg
    # - Anthropic/DashScope: via `client_kwargs`
    if config.base_url:
        if provider in ("anthropic", "dashscope"):
            model_kwargs["client_kwargs"] = {"base_url": config.base_url}
        else:
            model_kwargs["base_url"] = config.base_url

    # Temperature goes in generate_kwargs for some providers
    if config.temperature is not None:
        if provider == "anthropic":
            model_kwargs.setdefault("generate_kwargs", {})["temperature"] = config.temperature
        else:
            model_kwargs["temperature"] = config.temperature

    model = ModelCls(**model_kwargs)
    formatter = FormatterCls()

    # Patch formatter to ensure tool_result content blocks always have 'type'
    # field. Some proxies (e.g., ZStack) strictly require it per Anthropic spec.
    if provider == "anthropic":
        _patch_anthropic_formatter(formatter)

    return model, formatter


def _patch_anthropic_formatter(formatter: FormatterBase) -> None:
    """Patch AnthropicChatFormatter to ensure:

    1. Tool result content blocks always have a 'type' field.
    2. Every tool_use has a matching tool_result immediately after it.
       The Anthropic API strictly requires this pairing.
    """
    original_format = formatter._format

    async def _patched_format(msgs, **kwargs):
        result = await original_format(msgs, **kwargs)

        # --- Fix 1: Ensure tool_result content blocks have 'type' ---
        for msg in result:
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        content = block.get("content")
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and "type" not in item:
                                    if "text" in item:
                                        item["type"] = "text"

        # --- Fix 2: Ensure every tool_use has a matching tool_result ---
        # Collect all tool_result ids present in the entire conversation
        all_result_ids = set()
        for msg in result:
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tid = block.get("tool_use_id")
                    if tid:
                        all_result_ids.add(tid)

        # Walk messages and inject dummy tool_results where missing
        repaired = []
        for msg in result:
            repaired.append(msg)

            if msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue

            missing_ids = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tid = block.get("id")
                    if tid and tid not in all_result_ids:
                        missing_ids.append(tid)

            if missing_ids:
                repaired.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "content": [{"type": "text", "text": "(no result)"}],
                        }
                        for tid in missing_ids
                    ],
                })

        return repaired

    formatter._format = _patched_format


class CodingAgent:
    """High-level coding agent that wraps ReActAgent with coding-specific setup.

    This class handles:
    - Model/formatter creation from config
    - System prompt assembly with project context
    - Toolkit setup with coding tools
    - Agent lifecycle (init, reply, shutdown)
    """

    def __init__(
        self,
        model_config: ModelConfig,
        permissions_config: PermissionsConfig | None = None,
        toolkit: Toolkit | None = None,
        memory: MemoryBase | None = None,
        git_info: GitInfo | None = None,
        project_memory: str | None = None,
        max_iters: int = 30,
        name: str = "CodingAgent",
    ) -> None:
        """Initialize the CodingAgent.

        Args:
            model_config: Model provider configuration.
            permissions_config: Permission rules.
            toolkit: Pre-configured Toolkit (tools registered separately).
            memory: Custom memory instance.
            git_info: Pre-fetched git info.
            project_memory: Pre-loaded project memory content.
            max_iters: Max reasoning-acting iterations per reply.
            name: Agent name.
        """
        self.name = name
        self._model_config = model_config
        self._permissions_config = permissions_config

        # Create model and formatter
        self._model, self._formatter = create_model_and_formatter(model_config)

        # Build system prompt
        prompt_builder = SystemPromptBuilder(
            permissions_config=permissions_config,
        )
        self._toolkit = toolkit or Toolkit()
        tool_names = list(self._toolkit.tools.keys())

        self._sys_prompt = prompt_builder.build(
            git_info=git_info,
            project_memory=project_memory,
            tool_names=tool_names,
        )

        # Create the underlying ReActAgent
        self._agent = ReActAgent(
            name=name,
            sys_prompt=self._sys_prompt,
            model=self._model,
            formatter=self._formatter,
            toolkit=self._toolkit,
            memory=memory,
            max_iters=max_iters,
            parallel_tool_calls=True,
        )

    @property
    def agent(self) -> ReActAgent:
        """Access the underlying ReActAgent."""
        return self._agent

    @property
    def toolkit(self) -> Toolkit:
        """Access the toolkit."""
        return self._toolkit

    async def reply(self, user_input: str) -> "Msg":
        """Process user input and return agent response.

        Args:
            user_input: The user's message.

        Returns:
            Response Msg from the agent.
        """
        from agentscope.message import Msg

        user_msg = Msg(
            name="user",
            content=user_input,
            role="user",
        )

        # ReActAgent.reply() returns a single Msg (not a generator)
        return await self._agent.reply(user_msg)

    def update_system_prompt(
        self,
        git_info: GitInfo | None = None,
        project_memory: str | None = None,
        extra_context: str | None = None,
    ) -> None:
        """Update the system prompt with new context."""
        prompt_builder = SystemPromptBuilder(
            permissions_config=self._permissions_config,
        )
        tool_names = list(self._toolkit.tools.keys())
        self._sys_prompt = prompt_builder.build(
            git_info=git_info,
            project_memory=project_memory,
            tool_names=tool_names,
            extra_context=extra_context,
        )
        self._agent._sys_prompt = self._sys_prompt

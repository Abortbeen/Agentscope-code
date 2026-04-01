# -*- coding: utf-8 -*-
"""A2A (Agent-to-Agent) protocol support for CodeAgent.

Enables CodeAgent to act as an A2A-compliant agent that can be discovered
and invoked by other agents over HTTP.
"""
from .server import A2AServer
from .card import build_agent_card

__all__ = ["A2AServer", "build_agent_card"]

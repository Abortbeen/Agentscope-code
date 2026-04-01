# -*- coding: utf-8 -*-
"""Tracing, AgentScope Studio integration, and observability setup.

Implements Unit 16 from the plan.
- OpenTelemetry tracing via agentscope.init(tracing_url=...)
- AgentScope Studio via agentscope.init(studio_url=...)
- Auto-launch Studio subprocess if configured
"""
import asyncio
import logging
import os
import shutil
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)


def setup_studio(
    studio_url: str | None = None,
    auto_launch: bool = False,
    port: int = 7860,
) -> str | None:
    """Set up AgentScope Studio connection.

    If auto_launch is True and studio_url is not provided, attempts to
    start a local Studio instance.

    Args:
        studio_url: URL of an existing Studio instance.
        auto_launch: Whether to auto-launch Studio if not running.
        port: Port for auto-launched Studio.

    Returns:
        The Studio URL if connected, None otherwise.
    """
    if studio_url:
        # Test connection
        try:
            import requests
            resp = requests.get(f"{studio_url}/trpc/getRuns", timeout=3)
            if resp.ok:
                logger.info("Connected to AgentScope Studio at %s", studio_url)
                return studio_url
        except Exception:
            logger.warning(
                "Cannot reach Studio at %s, trying to launch...",
                studio_url,
            )
            if not auto_launch:
                return None

    if auto_launch:
        return _auto_launch_studio(port)

    return None


def _auto_launch_studio(port: int = 7860) -> str | None:
    """Launch AgentScope Studio as a background subprocess.

    Args:
        port: Port to launch on.

    Returns:
        Studio URL if launched successfully, None otherwise.
    """
    as_studio_bin = shutil.which("as_studio")
    if not as_studio_bin:
        logger.warning("as_studio binary not found. Install with: pip install agentscope[studio]")
        return None

    # Check if port is already in use
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            # Port in use, assume Studio is running
            url = f"http://localhost:{port}"
            logger.info("Studio port %d already in use, assuming running at %s", port, url)
            return url

    try:
        env = os.environ.copy()
        env["PORT"] = str(port)
        proc = subprocess.Popen(
            [as_studio_bin, "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        # Wait for Studio to start (up to 10 seconds)
        url = f"http://localhost:{port}"
        for _ in range(20):
            time.sleep(0.5)
            try:
                import requests
                resp = requests.get(f"{url}/trpc/getRuns", timeout=1)
                if resp.ok:
                    logger.info("Auto-launched AgentScope Studio at %s (PID: %d)", url, proc.pid)
                    return url
            except Exception:
                continue

        logger.warning("Studio started but not responding within 10s")
        return url  # Return URL anyway, may still be starting

    except Exception as e:
        logger.warning("Failed to auto-launch Studio: %s", e)
        return None


def setup_tracing(tracing_url: str | None = None) -> bool:
    """Set up OpenTelemetry tracing.

    Args:
        tracing_url: URL for the OTLP tracing endpoint.
            If None but Studio is connected, uses Studio's tracing endpoint.

    Returns:
        True if tracing was set up.
    """
    if not tracing_url:
        logger.debug("No tracing URL configured.")
        return False

    try:
        from agentscope.tracing import setup_tracing as _setup
        _setup(endpoint=tracing_url)
        logger.info("Tracing enabled at %s", tracing_url)
        return True
    except Exception as e:
        logger.warning("Failed to set up tracing: %s", e)
        return False


def init_observability(
    studio_url: str | None = None,
    auto_launch_studio: bool = False,
    studio_port: int = 7860,
    tracing_url: str | None = None,
    project: str = "codeagent",
    run_name: str | None = None,
) -> dict[str, Any]:
    """Initialize all observability features.

    This is the main entry point that sets up Studio + Tracing + agentscope.init.

    Args:
        studio_url: Studio URL.
        auto_launch_studio: Auto-launch Studio.
        studio_port: Port for auto-launched Studio.
        tracing_url: OTLP tracing URL.
        project: Project name for agentscope.
        run_name: Run name for agentscope.

    Returns:
        Dict with status: {studio_url, tracing_enabled, studio_connected}
    """
    result = {
        "studio_url": None,
        "studio_connected": False,
        "tracing_enabled": False,
    }

    # 1. Setup Studio
    actual_studio_url = setup_studio(
        studio_url=studio_url,
        auto_launch=auto_launch_studio,
        port=studio_port,
    )

    if actual_studio_url:
        result["studio_url"] = actual_studio_url
        result["studio_connected"] = True

    # 2. Initialize agentscope with Studio and tracing
    try:
        import agentscope
        init_kwargs = {
            "project": project,
        }
        if run_name:
            init_kwargs["name"] = run_name
        if actual_studio_url:
            init_kwargs["studio_url"] = actual_studio_url
        if tracing_url:
            init_kwargs["tracing_url"] = tracing_url

        if len(init_kwargs) > 1:  # More than just project
            agentscope.init(**init_kwargs)
            result["tracing_enabled"] = True
            logger.info("AgentScope initialized: %s", init_kwargs)
    except Exception as e:
        logger.warning("Failed to initialize agentscope observability: %s", e)

    return result

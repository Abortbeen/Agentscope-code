# -*- coding: utf-8 -*-
"""MCP (Model Context Protocol) server integration for CodeAgent.

Connects to MCP servers (stdio or SSE transport) and registers their
tools into an AgentScope Toolkit so the agent can call them like any
other tool.
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
from typing import Any, Dict, List, Optional, Sequence

from agentscope.tool import Toolkit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _StdioMCPClient:
    """Minimal MCP client that talks to a server over stdio (JSON-RPC)."""

    def __init__(self, command: List[str], env: Optional[Dict[str, str]] = None) -> None:
        self.command = command
        self.env = env
        self._proc: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._lock = threading.Lock()

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Launch the MCP server subprocess."""
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            text=True,
        )
        # Send initialize handshake
        self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "codeagent", "version": "0.1.0"},
        })

    def stop(self) -> None:
        """Terminate the server subprocess."""
        if self._proc and self._proc.poll() is None:
            try:
                self._send_notification("notifications/exit", {})
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                if self._proc.poll() is None:
                    self._proc.kill()

    # -- JSON-RPC transport --------------------------------------------------

    def _next_id(self) -> int:
        with self._lock:
            self._request_id += 1
            return self._request_id

    def _send_request(self, method: str, params: Any = None) -> Any:
        """Send a JSON-RPC request and return the result."""
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("MCP server process is not running")

        msg: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            msg["params"] = params

        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()

        # Read one line of response
        resp_line = self._proc.stdout.readline()
        if not resp_line:
            raise RuntimeError("MCP server closed stdout unexpectedly")

        resp = json.loads(resp_line)
        if "error" in resp:
            raise RuntimeError(f"MCP error: {resp['error']}")
        return resp.get("result")

    def _send_notification(self, method: str, params: Any = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if self._proc is None or self._proc.stdin is None:
            return
        msg: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        line = json.dumps(msg) + "\n"
        try:
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
        except BrokenPipeError:
            pass

    # -- MCP operations ------------------------------------------------------

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return the list of tools advertised by the server."""
        result = self._send_request("tools/list", {})
        return result.get("tools", []) if result else []

    def call_tool(self, name: str, arguments: Dict[str, Any] | None = None) -> Any:
        """Invoke a tool on the server and return the result."""
        result = self._send_request("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        return result


class _SSEMCPClient:
    """Minimal MCP client that talks to a server over SSE/HTTP."""

    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def start(self) -> None:
        """Verify the server is reachable."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception as exc:
            raise RuntimeError(
                f"Cannot reach MCP SSE server at {self.url}: {exc}"
            ) from exc

    def stop(self) -> None:
        pass  # HTTP is stateless

    def list_tools(self) -> List[Dict[str, Any]]:
        """List tools from the SSE server."""
        import urllib.request
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }).encode()
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        if "error" in result:
            raise RuntimeError(f"MCP error: {result['error']}")
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any] | None = None) -> Any:
        """Invoke a tool on the SSE server."""
        import urllib.request
        body = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }).encode()
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        if "error" in result:
            raise RuntimeError(f"MCP error: {result['error']}")
        return result.get("result")


# Keep track of active clients for cleanup
_active_clients: List[Any] = []

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _make_mcp_tool_caller(client: Any, tool_name: str):
    """Create a closure that calls a specific tool on an MCP server."""

    def _call(**kwargs: Any) -> Any:
        """Call the MCP tool with the provided arguments."""
        try:
            return client.call_tool(tool_name, kwargs)
        except Exception as exc:
            return {"error": str(exc)}

    _call.__name__ = tool_name
    _call.__qualname__ = tool_name
    return _call


def register_mcp_servers(
    toolkit: Toolkit,
    servers_config: Sequence[Dict[str, Any]],
) -> int:
    """Connect to MCP servers and register their tools in the toolkit.

    Each entry in *servers_config* is a dict with:
      - ``name``  – human-readable server name
      - ``command`` – list[str] for stdio transport  **or**
      - ``url``    – string URL for SSE transport
      - ``env``   – (optional) dict of environment variables (stdio only)

    Returns the total number of tools registered across all servers.

    Raises nothing – errors are logged and the offending server is skipped.
    """
    # Check if AgentScope Toolkit has native MCP support
    _has_native_mcp = hasattr(toolkit, "register_mcp_tool") or hasattr(
        toolkit, "connect_mcp_server"
    )

    total_registered = 0

    for server_cfg in servers_config:
        server_name = server_cfg.get("name", "unnamed")
        try:
            if _has_native_mcp:
                # Use AgentScope's built-in MCP support
                total_registered += _register_native(toolkit, server_cfg)
            else:
                # Fall back to our own wrapper
                total_registered += _register_wrapper(toolkit, server_cfg)
        except Exception as exc:
            logger.warning(
                "Failed to connect to MCP server %r: %s", server_name, exc,
            )

    return total_registered


def _register_native(toolkit: Toolkit, server_cfg: Dict[str, Any]) -> int:
    """Register tools using AgentScope's built-in MCP integration."""
    count = 0
    if hasattr(toolkit, "connect_mcp_server"):
        if "command" in server_cfg:
            toolkit.connect_mcp_server(
                server_name=server_cfg["name"],
                transport="stdio",
                command=server_cfg["command"],
            )
        elif "url" in server_cfg:
            toolkit.connect_mcp_server(
                server_name=server_cfg["name"],
                transport="sse",
                url=server_cfg["url"],
            )
        # Count tools (best-effort)
        count = len(getattr(toolkit, "tools", {}))
    return count


def _register_wrapper(toolkit: Toolkit, server_cfg: Dict[str, Any]) -> int:
    """Register tools using our lightweight MCP client wrapper."""
    server_name = server_cfg.get("name", "unnamed")
    client: Any

    if "command" in server_cfg:
        cmd = server_cfg["command"]
        if isinstance(cmd, str):
            cmd = cmd.split()
        client = _StdioMCPClient(
            command=cmd,
            env=server_cfg.get("env"),
        )
    elif "url" in server_cfg:
        client = _SSEMCPClient(url=server_cfg["url"])
    else:
        raise ValueError(
            f"MCP server {server_name!r} needs either 'command' or 'url'"
        )

    client.start()
    _active_clients.append(client)

    tools = client.list_tools()
    count = 0

    for tool_def in tools:
        tool_name = tool_def.get("name", "")
        if not tool_name:
            continue

        # Build a prefixed name to avoid collisions
        registered_name = f"mcp_{server_name}_{tool_name}"
        description = tool_def.get("description", f"MCP tool: {tool_name}")

        caller = _make_mcp_tool_caller(client, tool_name)

        try:
            toolkit.register_tool_function(
                tool_func=caller,
                func_name=registered_name,
                func_description=f"[MCP/{server_name}] {description}",
                group_name="mcp",
                namesake_strategy="skip",
            )
            count += 1
            logger.info(
                "Registered MCP tool %r from server %r",
                registered_name,
                server_name,
            )
        except Exception as exc:
            logger.warning(
                "Could not register MCP tool %r: %s", registered_name, exc,
            )

    logger.info(
        "MCP server %r: registered %d/%d tools",
        server_name,
        count,
        len(tools),
    )
    return count


def shutdown_mcp_servers() -> None:
    """Stop all active MCP server connections."""
    for client in _active_clients:
        try:
            client.stop()
        except Exception as exc:
            logger.debug("Error stopping MCP client: %s", exc)
    _active_clients.clear()

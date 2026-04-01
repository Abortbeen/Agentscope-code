# -*- coding: utf-8 -*-
"""A2A protocol HTTP server for CodeAgent.

Implements the A2A (Agent-to-Agent) protocol server that:
1. Serves the Agent Card at /.well-known/agent.json
2. Accepts task submissions at /a2a (JSON-RPC)
3. Manages task lifecycle (submitted → working → completed/failed)
4. Supports streaming responses via SSE

Uses aiohttp for the HTTP server (lightweight, async-native).
"""
import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class A2ATask:
    """An A2A task received from a remote agent."""
    id: str
    prompt: str
    status: str = "submitted"  # submitted, working, completed, failed, canceled
    result: str | None = None
    artifacts: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class A2AServer:
    """HTTP server implementing the A2A protocol.

    Serves:
    - GET /.well-known/agent.json — Agent Card discovery
    - POST /a2a — JSON-RPC task endpoint (tasks/send, tasks/get, tasks/cancel)

    Args:
        agent_card: The Agent Card dict.
        task_handler: Async function that processes a prompt and returns a result string.
        host: Bind host.
        port: Bind port.
    """

    def __init__(
        self,
        agent_card: dict[str, Any],
        task_handler: Callable[[str], Awaitable[str]],
        host: str = "0.0.0.0",
        port: int = 7861,
    ) -> None:
        self._agent_card = agent_card
        self._task_handler = task_handler
        self._host = host
        self._port = port
        self._tasks: dict[str, A2ATask] = {}
        self._runner = None
        self._site = None

    async def start(self) -> None:
        """Start the A2A HTTP server."""
        try:
            from aiohttp import web
        except ImportError:
            logger.error("aiohttp not installed. Run: pip install aiohttp")
            return

        app = web.Application()
        app.router.add_get("/.well-known/agent.json", self._handle_agent_card)
        app.router.add_post("/a2a", self._handle_a2a_rpc)
        app.router.add_get("/health", self._handle_health)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        logger.info(
            "A2A server started at http://%s:%d",
            self._host, self._port,
        )

    async def stop(self) -> None:
        """Stop the A2A HTTP server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            logger.info("A2A server stopped.")

    async def _handle_agent_card(self, request) -> Any:
        """Serve the Agent Card."""
        from aiohttp import web
        return web.json_response(self._agent_card)

    async def _handle_health(self, request) -> Any:
        """Health check endpoint."""
        from aiohttp import web
        return web.json_response({
            "status": "ok",
            "active_tasks": len([t for t in self._tasks.values() if t.status == "working"]),
            "total_tasks": len(self._tasks),
        })

    async def _handle_a2a_rpc(self, request) -> Any:
        """Handle A2A JSON-RPC requests."""
        from aiohttp import web

        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                _jsonrpc_error(None, -32700, "Parse error"),
                status=400,
            )

        method = body.get("method")
        params = body.get("params", {})
        rpc_id = body.get("id")

        if method == "tasks/send":
            return await self._handle_task_send(rpc_id, params)
        elif method == "tasks/get":
            return await self._handle_task_get(rpc_id, params)
        elif method == "tasks/cancel":
            return await self._handle_task_cancel(rpc_id, params)
        else:
            return web.json_response(
                _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}"),
            )

    async def _handle_task_send(self, rpc_id: Any, params: dict) -> Any:
        """Handle tasks/send — submit a new task or continue existing."""
        from aiohttp import web

        task_id = params.get("id") or str(uuid.uuid4())

        # Extract prompt from message parts
        message = params.get("message", {})
        parts = message.get("parts", [])
        prompt = ""
        for part in parts:
            if part.get("type") == "text":
                prompt += part.get("text", "")

        if not prompt:
            return web.json_response(
                _jsonrpc_error(rpc_id, -32602, "No text content in message"),
            )

        # Create task
        task = A2ATask(id=task_id, prompt=prompt, status="working")
        self._tasks[task_id] = task

        # Process asynchronously
        asyncio.create_task(self._process_task(task))

        return web.json_response(_jsonrpc_result(rpc_id, {
            "id": task.id,
            "status": {"state": task.status},
            "history": [message],
        }))

    async def _handle_task_get(self, rpc_id: Any, params: dict) -> Any:
        """Handle tasks/get — get task status and result."""
        from aiohttp import web

        task_id = params.get("id")
        task = self._tasks.get(task_id)
        if not task:
            return web.json_response(
                _jsonrpc_error(rpc_id, -32602, f"Task not found: {task_id}"),
            )

        result = {
            "id": task.id,
            "status": {"state": task.status},
            "artifacts": task.artifacts,
        }

        return web.json_response(_jsonrpc_result(rpc_id, result))

    async def _handle_task_cancel(self, rpc_id: Any, params: dict) -> Any:
        """Handle tasks/cancel — cancel a running task."""
        from aiohttp import web

        task_id = params.get("id")
        task = self._tasks.get(task_id)
        if not task:
            return web.json_response(
                _jsonrpc_error(rpc_id, -32602, f"Task not found: {task_id}"),
            )

        task.status = "canceled"
        task.updated_at = datetime.now().isoformat()

        return web.json_response(_jsonrpc_result(rpc_id, {
            "id": task.id,
            "status": {"state": "canceled"},
        }))

    async def _process_task(self, task: A2ATask) -> None:
        """Process a task using the agent handler."""
        try:
            result = await self._task_handler(task.prompt)
            task.result = result
            task.status = "completed"
            task.artifacts = [{
                "parts": [{"type": "text", "text": result}],
                "index": 0,
            }]
        except Exception as e:
            task.status = "failed"
            task.result = f"Error: {e}"
            task.artifacts = [{
                "parts": [{"type": "text", "text": f"Error: {e}"}],
                "index": 0,
            }]
            logger.error("Task %s failed: %s", task.id, e)
        finally:
            task.updated_at = datetime.now().isoformat()


def _jsonrpc_result(rpc_id: Any, result: Any) -> dict:
    """Build a JSON-RPC success response."""
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "result": result,
    }


def _jsonrpc_error(rpc_id: Any, code: int, message: str) -> dict:
    """Build a JSON-RPC error response."""
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {"code": code, "message": message},
    }

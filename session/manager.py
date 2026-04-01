# -*- coding: utf-8 -*-
"""Session management - save/resume conversation sessions.

Implements R30-R31 from the plan.
Uses AgentScope's JSONSession under the hood.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class SessionManager:
    """Manages conversation session persistence."""

    def __init__(self, storage_dir: str | None = None) -> None:
        self._storage_dir = Path(
            storage_dir
            or os.path.expanduser("~/.config/codeagent/sessions")
        )
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._current_session_id: str | None = None

    @property
    def current_session_id(self) -> str | None:
        return self._current_session_id

    def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_session_id = session_id
        session_dir = self._storage_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_id

    def save_session(
        self,
        session_id: str | None = None,
        agent_state: dict | None = None,
        conversation: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """Save session state to disk.

        Args:
            session_id: Session ID. Uses current if None.
            agent_state: Agent state dict.
            conversation: Conversation history.
            metadata: Extra metadata (model, cwd, etc).

        Returns:
            True if successful.
        """
        sid = session_id or self._current_session_id
        if not sid:
            return False

        session_dir = self._storage_dir / sid
        session_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "id": sid,
            "saved_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "agent_state": agent_state or {},
            "conversation": conversation or [],
        }

        try:
            with open(session_dir / "session.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            return True
        except OSError:
            return False

    def load_session(self, session_id: str) -> dict | None:
        """Load a session from disk.

        Args:
            session_id: The session ID or 'latest'.

        Returns:
            Session data dict or None.
        """
        if session_id == "latest":
            session_id = self._get_latest_session_id()
            if not session_id:
                return None

        session_file = self._storage_dir / session_id / "session.json"
        if not session_file.exists():
            return None

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent sessions.

        Returns:
            List of session summaries.
        """
        sessions = []
        if not self._storage_dir.exists():
            return sessions

        for entry in sorted(
            self._storage_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            if not entry.is_dir():
                continue
            session_file = entry / "session.json"
            if session_file.exists():
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append({
                        "id": entry.name,
                        "saved_at": data.get("saved_at", ""),
                        "metadata": data.get("metadata", {}),
                        "messages": len(data.get("conversation", [])),
                    })
                except (json.JSONDecodeError, OSError):
                    pass

            if len(sessions) >= limit:
                break

        return sessions

    def _get_latest_session_id(self) -> str | None:
        """Get the most recent session ID."""
        sessions = self.list_sessions(limit=1)
        return sessions[0]["id"] if sessions else None

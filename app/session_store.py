"""
Copilot Session Store — server-side multi-turn conversation memory (Teammate 4).

Two layers:
1. In-memory store (this module) — fast, always available, per-process.
2. `ai_copilot_sessions` table via TSPClient — durable persistence, best-effort.

The endpoint hydrates the in-memory store from the DB on a cold start
(e.g. after a service restart), so conversations survive restarts when
the table exists, and degrade gracefully to memory-only when it doesn't.
"""

import uuid
from typing import Dict, List

# Keep the last N turns per session in the prompt window.
MAX_TURNS_PER_SESSION = 20


class SessionStore:
    """In-memory conversation store keyed by session_id."""

    def __init__(self, max_turns: int = MAX_TURNS_PER_SESSION):
        self._sessions: Dict[str, List[Dict[str, str]]] = {}
        self._max_turns = max_turns

    @staticmethod
    def new_session_id() -> str:
        return str(uuid.uuid4())

    def get(self, session_id: str) -> List[Dict[str, str]]:
        """Return the turn list for a session (empty list if unknown)."""
        return list(self._sessions.get(session_id, []))

    def has(self, session_id: str) -> bool:
        return session_id in self._sessions

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append one turn ({role, content}) and trim to the window size."""
        turns = self._sessions.setdefault(session_id, [])
        turns.append({"role": role, "content": content})
        if len(turns) > self._max_turns:
            del turns[: len(turns) - self._max_turns]

    def hydrate(self, session_id: str, turns: List[Dict[str, str]]) -> None:
        """Seed a session from DB history (only if not already in memory)."""
        if session_id not in self._sessions and turns:
            self._sessions[session_id] = list(turns)[-self._max_turns:]

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# Module-level singleton used by the FastAPI app.
session_store = SessionStore()

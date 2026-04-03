"""
WebSocket connection manager for real-time live score broadcasting.

Architecture:
  - A background task polls CricAPI every POLL_INTERVAL seconds during match windows
  - After each poll, it compares the new data against the last broadcast
  - Only broadcasts to WebSocket clients when scores actually change (new ball/wicket/state)
  - Clients auto-reconnect on disconnect (handled frontend-side)
  - LiveSnapshot records are persisted on each poll for post-match analysis

This replaces the frontend's 30-second HTTP polling with server-push via WebSocket,
reducing API calls and latency. Change-detection ensures zero redundant pushes.
"""

import asyncio
import logging
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("ws_manager")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL = 20   # Seconds between CricAPI polls (matches SCORE_CACHE_TTL)
HEARTBEAT_INTERVAL = 15  # Send heartbeat every N seconds to keep connection alive

# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------


class LiveScoreManager:
    """Manages WebSocket connections and broadcasts live score updates.

    Thread-safe for asyncio — all methods are coroutines or called from
    the event loop.
    """

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._poll_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._latest_state: dict | None = None  # Cache for new connections
        self._last_fingerprint: str | None = None  # Change detection

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket):
        """Accept a new WebSocket connection and send cached state."""
        await ws.accept()
        self._connections.add(ws)
        print(f"WS client connected ({self.connection_count} total)")

        # Send latest state immediately so client doesn't wait for next poll
        if self._latest_state:
            try:
                initial = {**self._latest_state, "type": "live_update"}
                await ws.send_json(initial)
            except Exception:
                pass

    def disconnect(self, ws: WebSocket):
        """Remove a disconnected client."""
        self._connections.discard(ws)
        print(f"WS client disconnected ({self.connection_count} total)")

    async def broadcast(self, data: dict):
        """Send data to all connected clients, removing dead connections."""
        self._latest_state = data
        dead: list[WebSocket] = []

        # Snapshot to avoid set mutation during async iteration
        for ws in list(self._connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.discard(ws)

    async def start_polling(self):
        """Start the background CricAPI polling loop and server heartbeat.

        Only polls during match windows (checked by live_tracker).
        Broadcasts results to all connected WebSocket clients.
        """
        if self._poll_task and not self._poll_task.done():
            return  # Already running

        self._poll_task = asyncio.create_task(self._poll_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        print("WS live score polling + heartbeat started")

    async def stop_polling(self):
        """Stop the background polling and heartbeat loops."""
        for task in (self._poll_task, self._heartbeat_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        print("WS live score polling + heartbeat stopped")

    @staticmethod
    def _score_fingerprint(payload: dict) -> str:
        """Build a fingerprint from live match scores for change detection.

        Captures match_id + innings + runs + wickets + overs + state for each
        live match. Also includes match counts to detect status transitions
        (e.g. live → result, fixture → live).
        """
        live = payload.get("live", [])
        parts: list[str] = []

        for m in sorted(live, key=lambda x: x.get("match_id", "")):
            score = m.get("current_score") or {}
            first = m.get("first_innings_score") or {}
            parts.append(
                f"{m.get('match_id')}:"
                f"{m.get('innings', 0)}:"
                f"{score.get('runs', 0)}:{score.get('wickets', 0)}:{score.get('overs', 0)}:"
                f"{first.get('runs', 0)}:{first.get('wickets', 0)}:{first.get('overs', 0)}:"
                f"{m.get('state', '')}"
            )

        # Detect fixture→live or live→result transitions
        parts.append(f"u:{len(payload.get('upcoming', []))}")
        parts.append(f"r:{len(payload.get('recent_results', []))}")
        return "|".join(parts)

    async def _heartbeat_loop(self):
        """Send periodic server→client pings to keep connections alive.

        Railway / load balancers may close idle WebSocket connections.
        This ensures there is always server-initiated traffic even when
        no score changes are being broadcast.
        """
        while True:
            try:
                dead: list[WebSocket] = []
                for ws in list(self._connections):
                    try:
                        await ws.send_json({"type": "heartbeat"})
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    self._connections.discard(ws)
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                break

    async def _poll_loop(self):
        """Background loop: fetch scores, broadcast only when data changes.

        Polls CricAPI every POLL_INTERVAL seconds. After each fetch, compares
        a fingerprint (runs/wickets/overs per match) against the last broadcast.
        Only pushes to clients when the score actually changed — e.g. a new
        ball was bowled, a wicket fell, or a match state transitioned.
        """
        from app.services.live_tracker import build_scores_payload

        while True:
            try:
                print(f"WS poll tick — {self.connection_count} client(s), fetching scores...")
                if self._connections:
                    # Reuses the same payload builder as GET /live/scores
                    payload = await build_scores_payload()
                    fingerprint = self._score_fingerprint(payload)

                    if fingerprint != self._last_fingerprint:
                        # Score changed — push immediately
                        self._last_fingerprint = fingerprint
                        payload["type"] = "live_update"
                        payload["clients"] = self.connection_count
                        await self.broadcast(payload)
                        print(
                            f"Score change detected — broadcast to {self.connection_count} clients"
                        )
                    else:
                        logger.debug("No score change, skipping broadcast")
                else:
                    print(f"WS poll tick (manager id={id(self)}) — no clients connected, skipping")

                await asyncio.sleep(POLL_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WS poll error: {e}")
                await asyncio.sleep(POLL_INTERVAL)


# Singleton instance
manager = LiveScoreManager()

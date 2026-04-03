"""
WebSocket connection manager for real-time live score broadcasting.

Architecture:
  - A background task polls CricAPI every POLL_INTERVAL seconds during match windows
  - On each poll, it broadcasts the latest match states to all connected WebSocket clients
  - Clients auto-reconnect on disconnect (handled frontend-side)
  - LiveSnapshot records are persisted on each poll for post-match analysis

This replaces the frontend's 30-second HTTP polling with server-push via WebSocket,
reducing API calls and latency.
"""

import asyncio
import logging
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("ws_manager")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL = 30   # Seconds between CricAPI polls during match windows
HEARTBEAT_INTERVAL = 15  # Send ping every N seconds to keep connection alive

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
        self._latest_state: dict | None = None  # Cache for new connections

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket):
        """Accept a new WebSocket connection and send cached state."""
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"WS client connected ({self.connection_count} total)")

        # Send latest state immediately so client doesn't wait for next poll
        if self._latest_state:
            try:
                await ws.send_json(self._latest_state)
            except Exception:
                pass

    def disconnect(self, ws: WebSocket):
        """Remove a disconnected client."""
        self._connections.discard(ws)
        logger.info(f"WS client disconnected ({self.connection_count} total)")

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
        """Start the background CricAPI polling loop.

        Only polls during match windows (checked by live_tracker).
        Broadcasts results to all connected WebSocket clients.
        """
        if self._poll_task and not self._poll_task.done():
            return  # Already running

        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("WS live score polling started")

    async def stop_polling(self):
        """Stop the background polling loop."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("WS live score polling stopped")

    async def _poll_loop(self):
        """Background loop: fetch scores via shared helper, broadcast to clients."""
        from app.services.live_tracker import build_scores_payload

        while True:
            try:
                if self._connections:
                    # Reuses the same payload builder as GET /live/scores
                    payload = await build_scores_payload()
                    payload["type"] = "live_update"
                    payload["clients"] = self.connection_count
                    await self.broadcast(payload)

                await asyncio.sleep(POLL_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WS poll error: {e}")
                await asyncio.sleep(POLL_INTERVAL)


# Singleton instance
manager = LiveScoreManager()

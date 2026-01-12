"""
Server-Sent Events (SSE) broadcaster for real-time notifications.

Maintains in-memory queues for connected clients and broadcasts events.
"""

from __future__ import annotations
import asyncio
import json
import logging
from typing import Dict, Set, Optional

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Simple in-memory broadcaster for SSE events."""

    def __init__(self):
        # Map of client_id -> asyncio.Queue
        self._queues: Dict[str, asyncio.Queue] = {}
        # Track active connections
        self._active: Set[str] = set()

    def subscribe(self, client_id: str) -> asyncio.Queue:
        """Subscribe a client and return a queue for receiving events."""
        if client_id not in self._queues:
            self._queues[client_id] = asyncio.Queue()
        self._active.add(client_id)
        logger.debug(
            f"Client {client_id} subscribed. Total clients: {len(self._active)}"
        )
        return self._queues[client_id]

    def unsubscribe(self, client_id: str):
        """Unsubscribe a client."""
        if client_id in self._queues:
            del self._queues[client_id]
        self._active.discard(client_id)
        logger.debug(
            f"Client {client_id} unsubscribed. Total clients: {len(self._active)}"
        )

    async def broadcast(self, event_type: str, data: dict):
        """Broadcast an event to all connected clients."""
        if not self._active:
            logger.debug(f"No active clients to broadcast {event_type} to")
            return

        message = {
            "type": event_type,
            "data": data,
        }
        message_json = json.dumps(message)

        # Put message in all queues
        disconnected = []
        for client_id, queue in self._queues.items():
            try:
                await queue.put(message_json)
            except Exception as e:
                logger.warning(f"Failed to send to client {client_id}: {e}")
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            self.unsubscribe(client_id)

        logger.info(
            f"Broadcasted {event_type} to {len(self._active)} clients. " f"Data: {data}"
        )

    def get_active_count(self) -> int:
        """Get number of active connections."""
        return len(self._active)


# Global broadcaster instance
broadcaster = SSEBroadcaster()

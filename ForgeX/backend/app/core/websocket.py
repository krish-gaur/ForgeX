
"""WebSocket hub for per-investigation job and AI status updates."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.auth import decode_token
from app.core.logging import get_logger

log = get_logger("ws")
router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections grouped by investigation ID."""

    def __init__(self) -> None:
        self._conns: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        investigation_id: str,
        ws: WebSocket,
    ) -> None:
        await ws.accept()

        async with self._lock:
            self._conns.setdefault(investigation_id, set()).add(ws)

        log.info("ws_connect", investigation_id=investigation_id)

    async def disconnect(
        self,
        investigation_id: str,
        ws: WebSocket,
    ) -> None:
        async with self._lock:
            connections = self._conns.get(investigation_id)

            if connections is not None:
                connections.discard(ws)

                # Avoid retaining empty investigation groups.
                if not connections:
                    self._conns.pop(investigation_id, None)

        log.info("ws_disconnect", investigation_id=investigation_id)

    async def broadcast(
        self,
        investigation_id: str,
        message: dict[str, Any],
    ) -> None:
        """Send a JSON message to every live connection in an investigation."""
        try:
            payload = json.dumps(message, separators=(",", ":"), default=str)
        except (TypeError, ValueError):
            log.warning(
                "ws_serialize_failed",
                investigation_id=investigation_id,
            )
            return

        async with self._lock:
            targets = list(self._conns.get(investigation_id, set()))

        if not targets:
            return

        async def send_one(ws: WebSocket) -> bool:
            try:
                if (
                    ws.client_state != WebSocketState.CONNECTED
                    or ws.application_state != WebSocketState.CONNECTED
                ):
                    return False

                await ws.send_text(payload)
                return True
            except Exception:  # noqa: BLE001
                return False

        results = await asyncio.gather(
            *(send_one(ws) for ws in targets)
        )

        dead = [
            ws
            for ws, succeeded in zip(targets, results)
            if not succeeded
        ]

        if dead:
            async with self._lock:
                current = self._conns.get(investigation_id)

                if current is not None:
                    current.difference_update(dead)

                    if not current:
                        self._conns.pop(investigation_id, None)

    async def broadcast_all(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all connected investigations."""
        async with self._lock:
            investigation_ids = list(self._conns.keys())

        await asyncio.gather(
            *(
                self.broadcast(investigation_id, message)
                for investigation_id in investigation_ids
            )
        )


manager = ConnectionManager()


def authenticate_websocket_token(token: str) -> dict[str, Any]:
    """Validate an access token using the application's existing auth helper."""
    claims = decode_token(token, "access")

    if not isinstance(claims, dict):
        raise ValueError("Invalid access-token claims")

    return claims


async def authorize_investigation(
    claims: dict[str, Any],
    investigation_id: str,
) -> bool:
    """
    TODO: Integrate the existing database-backed authorization service.

    Verify that the authenticated user can access this investigation,
    including tenant boundaries and the user's current permissions.

    Fail closed until that integration is implemented.
    """
    return False


@router.websocket("/ws")
async def ws_endpoint(
    ws: WebSocket,
    investigation_id: str | None = None,
) -> None:
    token = ws.query_params.get("token")

    if not token or not investigation_id:
        await ws.close(code=4401)
        return

    try:
        claims = authenticate_websocket_token(token)
    except Exception:  # noqa: BLE001
        log.warning("ws_auth_failed")
        await ws.close(code=4401)
        return

    try:
        allowed = await authorize_investigation(claims, investigation_id)
    except Exception:  # noqa: BLE001
        log.warning("ws_authorization_error", investigation_id=investigation_id)
        await ws.close(code=1011)
        return

    if not allowed:
        log.warning("ws_access_denied", investigation_id=investigation_id)
        await ws.close(code=4403)
        return

    await manager.connect(investigation_id, ws)

    try:
        while True:
            # Receive client messages to detect disconnects.
            # Do not trust client-supplied messages as evidence or job events.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.warning("ws_connection_error", investigation_id=investigation_id)
    finally:
        with suppress(Exception):
            await manager.disconnect(investigation_id, ws)

"""WebSocket hub: per-investigation live job/AI status fan-out (architecture §03/§07)."""
from __future__ import annotations

import asyncio
import json
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.auth import decode_token
from app.core.logging import get_logger

log = get_logger("ws")
router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, investigation_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._conns.setdefault(investigation_id, set()).add(ws)
        log.info("ws_connect", investigation_id=investigation_id)

    async def disconnect(self, investigation_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.get(investigation_id, set()).discard(ws)

    async def broadcast(self, investigation_id: str, message: dict) -> None:
        async with self._lock:
            targets = list(self._conns.get(investigation_id, set()))
        dead = []
        for ws in targets:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps(message))
            except Exception:  # noqa: BLE001 — a dead socket must not break fan-out
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._conns.get(investigation_id, set()).discard(ws)

    async def broadcast_all(self, message: dict) -> None:
        async with self._lock:
            ids = list(self._conns.keys())
        for inv in ids:
            await self.broadcast(inv, message)


manager = ConnectionManager()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket, investigation_id: str | None = None) -> None:
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4401)
        return
    try:
        decode_token(token, "access")
    except Exception:  # noqa: BLE001
        await ws.close(code=4401)
        return
    inv = investigation_id or "_global"
    await manager.connect(inv, ws)
    try:
        while True:
            await ws.receive_text()  # client ping/keepalive; server ignores content
    except WebSocketDisconnect:
        pass
    finally:
        with suppress(Exception):
            await manager.disconnect(inv, ws)

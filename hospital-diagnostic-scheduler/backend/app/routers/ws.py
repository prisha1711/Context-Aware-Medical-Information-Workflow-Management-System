from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jwt import PyJWTError

from ..security import decode_token
from ..services.ws import hub

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = ""):
    try:
        decode_token(token)
    except PyJWTError:
        await ws.close(code=4401)
        return
    await ws.accept()
    hub.conns.add(ws)
    try:
        while True:
            await ws.receive_text()      # keep-alive pings from the client
    except WebSocketDisconnect:
        hub.conns.discard(ws)

"""WebSocket fan-out. In-process by default; if REDIS_URL is set, events go through Redis pub/sub so several
API workers can serve the same dashboard. (Redis is optional - one worker needs nothing.)"""
import asyncio
import json

from ..config import settings


class Hub:
    def __init__(self):
        self.conns = set()
        self.loop = None
        self.redis = None

    async def start(self):
        self.loop = asyncio.get_running_loop()
        if settings.redis_url:
            import redis.asyncio as aioredis
            self.redis = aioredis.from_url(settings.redis_url)
            self.loop.create_task(self._listen())

    async def _listen(self):
        ps = self.redis.pubsub()
        await ps.subscribe("hds")
        async for m in ps.listen():
            if m["type"] == "message":
                data = m["data"]
                await self._fanout(data.decode() if isinstance(data, bytes) else data)

    async def _fanout(self, text: str):
        for ws in list(self.conns):
            try:
                await ws.send_text(text)
            except Exception:
                self.conns.discard(ws)

    def publish(self, msg: dict):
        """Callable from sync request handlers (they run in a worker thread)."""
        if not self.loop:
            return
        text = json.dumps(msg, default=str)
        coro = self.redis.publish("hds", text) if self.redis else self._fanout(text)
        asyncio.run_coroutine_threadsafe(coro, self.loop)


hub = Hub()

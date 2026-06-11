import asyncio
import logging
from fastapi import WebSocket

logger = logging.getLogger("manager.ws")

class InstanceWSManager:
    def __init__(self):
        self.active: dict[str, list[tuple[WebSocket, asyncio.Task]]] = {}

    async def connect(self, instance_id: str, ws: WebSocket):
        await ws.accept()
        keep_alive_task = asyncio.create_task(self._keep_alive(instance_id, ws))
        self.active.setdefault(instance_id, []).append((ws, keep_alive_task))

    def disconnect(self, instance_id: str, ws: WebSocket):
        if instance_id in self.active:
            for pair in self.active[instance_id]:
                if pair[0] == ws:
                    pair[1].cancel()
                    self.active[instance_id].remove(pair)
                    break
            if not self.active[instance_id]:
                del self.active[instance_id]

    async def broadcast(self, instance_id: str, payload: dict):
        if instance_id not in self.active:
            return
        for ws, _ in self.active[instance_id].copy():
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(instance_id, ws)

    async def _keep_alive(self, instance_id: str, ws: WebSocket):
        try:
            while True:
                await asyncio.sleep(25)
                await ws.send_json({"event": "ping"})
        except asyncio.CancelledError:
            logger.debug(f"Keep-alive for {instance_id} cancelled cleanly.")
        except Exception as e:
            logger.error(f"WS keep-alive error ({instance_id}): {e}")
            self.disconnect(instance_id, ws)

ws_manager = InstanceWSManager()

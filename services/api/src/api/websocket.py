"""WebSocket telemetry stream."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Union

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.metrics import WS_CONNECTIONS_ACTIVE, WS_MESSAGES_SENT, WS_CLIENT_DROPPED
from api.redis_client import get_client

logger = logging.getLogger(__name__)

router = APIRouter()

SEND_QUEUE_MAX = 100
BATCH_INTERVAL_MS = 250


@dataclass
class SubscribeAction:
    equipment_ids: list[str]


@dataclass
class UnsubscribeAction:
    equipment_ids: list[str]


@dataclass
class SubscribeAllAction:
    pass


ClientMessage = Union[SubscribeAction, UnsubscribeAction, SubscribeAllAction]


def parse_client_message(raw: str) -> ClientMessage:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("invalid json")
    action = data.get("action")
    if action == "subscribe":
        return SubscribeAction(equipment_ids=data.get("equipment_ids", []))
    if action == "unsubscribe":
        return UnsubscribeAction(equipment_ids=data.get("equipment_ids", []))
    if action == "subscribe_all":
        return SubscribeAllAction()
    raise ValueError(f"unknown action: {action}")


@router.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket) -> None:
    await ws.accept()
    WS_CONNECTIONS_ACTIVE.inc()
    client = get_client()
    pubsub = client.pubsub()
    subscribed: set[str] = set()
    all_mode = False

    send_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SEND_QUEUE_MAX)

    async def reader() -> None:
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    action = parse_client_message(raw)
                except ValueError as e:
                    await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
                    continue
                nonlocal all_mode
                if isinstance(action, SubscribeAction):
                    for eid in action.equipment_ids:
                        ch = f"telemetry:{eid}"
                        if ch not in subscribed:
                            await pubsub.subscribe(ch)
                            subscribed.add(ch)
                    await ws.send_text(json.dumps({"type": "ack", "action": "subscribe", "equipment_ids": action.equipment_ids}))
                elif isinstance(action, UnsubscribeAction):
                    for eid in action.equipment_ids:
                        ch = f"telemetry:{eid}"
                        if ch in subscribed:
                            await pubsub.unsubscribe(ch)
                            subscribed.discard(ch)
                    await ws.send_text(json.dumps({"type": "ack", "action": "unsubscribe", "equipment_ids": action.equipment_ids}))
                elif isinstance(action, SubscribeAllAction):
                    await pubsub.psubscribe("telemetry:*")
                    all_mode = True
                    await ws.send_text(json.dumps({"type": "ack", "action": "subscribe_all"}))
        except WebSocketDisconnect:
            pass

    async def forwarder() -> None:
        try:
            while True:
                # Don't call get_message before any subscription is registered —
                # redis-py raises RuntimeError if the connection isn't set up yet.
                if not pubsub.subscribed:
                    await asyncio.sleep(0.1)
                    continue
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue
                data = message.get("data")
                if not data:
                    continue
                try:
                    inner = json.loads(data)
                except json.JSONDecodeError:
                    continue
                out = {
                    "type": "telemetry",
                    "equipment_id": inner.get("equipment_id"),
                    "time": inner.get("time"),
                    "status": inner.get("status"),
                    "batch_id": inner.get("batch_id"),
                    "unit_id": inner.get("unit_id"),
                    "metrics": inner.get("metrics", {}),
                }
                try:
                    send_queue.put_nowait(json.dumps(out))
                except asyncio.QueueFull:
                    try:
                        send_queue.get_nowait()  # drop oldest
                    except asyncio.QueueEmpty:
                        pass
                    WS_CLIENT_DROPPED.labels(reason="queue_full").inc()
                    send_queue.put_nowait(json.dumps(out))
        except Exception:
            logger.exception("forwarder error")

    async def sender() -> None:
        try:
            while True:
                msg = await send_queue.get()
                await ws.send_text(msg)
                WS_MESSAGES_SENT.inc()
        except WebSocketDisconnect:
            pass

    reader_task = asyncio.create_task(reader())
    forwarder_task = asyncio.create_task(forwarder())
    sender_task = asyncio.create_task(sender())

    done, pending = await asyncio.wait(
        {reader_task, forwarder_task, sender_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for t in pending:
        t.cancel()
    WS_CONNECTIONS_ACTIVE.dec()
    try:
        await pubsub.close()
    except Exception:
        pass

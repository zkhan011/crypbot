"""Configurable BingX WebSocket transport without invented subscriptions/auth."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import random
import time
import zlib
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

import websockets
from websockets.exceptions import ConnectionClosed


class WebSocketConnection(Protocol):
    async def send(self, message: str | bytes) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self) -> None: ...


class WebSocketState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    STOPPED = "STOPPED"


class BingXWebSocketDisabled(RuntimeError):
    pass


@dataclass(frozen=True)
class WebSocketHealth:
    state: WebSocketState
    last_message_age_seconds: Decimal | None
    reconnects: int
    subscriptions: int


class BingXWebSocketClient:
    """Transport/recovery layer; payloads must be supplied from reviewed config.

    Private authentication and stream payloads are disabled unless explicitly
    configured. REST reconciliation remains the recovery authority.
    """

    def __init__(
        self,
        url: str,
        *,
        subscriptions_enabled: bool = False,
        private_stream_enabled: bool = False,
        stale_seconds: Decimal = Decimal("15"),
        max_backoff_seconds: Decimal = Decimal("30"),
        connector: Callable[[str], Awaitable[WebSocketConnection]] | None = None,
        heartbeat_payload: str | None = None,
        rest_recovery: Callable[[], Awaitable[None]] | None = None,
        event_validator: Callable[[dict[str, Any]], bool] | None = None,
        jitter: Callable[[], Decimal] | None = None,
    ) -> None:
        if not url.startswith("wss://"):
            raise ValueError("BingX WebSocket URL must use wss")
        if stale_seconds <= 0 or max_backoff_seconds <= 0:
            raise ValueError("WebSocket timing values must be positive")
        self.url = url
        self.subscriptions_enabled = subscriptions_enabled
        self.private_stream_enabled = private_stream_enabled
        self.stale_seconds = stale_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self._connector = connector or websockets.connect
        self._heartbeat_payload = heartbeat_payload
        self._rest_recovery = rest_recovery
        self._event_validator = event_validator
        self._jitter = jitter or (lambda: Decimal(str(random.random())) * Decimal("0.2"))
        self._connection: WebSocketConnection | None = None
        self._subscriptions: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable[[dict[str, Any]], Awaitable[None]]] = {}
        self._seen: set[str] = set()
        self._seen_order: deque[str] = deque(maxlen=2_000)
        self._last_message: Decimal | None = None
        self.state = WebSocketState.DISCONNECTED
        self.reconnects = 0
        self._stop = asyncio.Event()

    @staticmethod
    def _now() -> Decimal:
        return Decimal(str(time.monotonic()))

    @staticmethod
    def decode(message: str | bytes) -> dict[str, Any]:
        if isinstance(message, bytes):
            decoded: bytes
            try:
                decoded = gzip.decompress(message)
            except (gzip.BadGzipFile, OSError):
                try:
                    decoded = zlib.decompress(message, -zlib.MAX_WBITS)
                except zlib.error:
                    decoded = message
            text = decoded.decode("utf-8")
        else:
            text = message
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("WebSocket event must be an object")
        return value

    async def connect(self) -> None:
        self.state = WebSocketState.CONNECTING
        self._connection = await self._connector(self.url)
        self.state = WebSocketState.CONNECTED
        self._last_message = self._now()
        await self._resubscribe()

    async def subscribe(
        self,
        logical_stream: str,
        payload: dict[str, Any],
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        private: bool = False,
    ) -> None:
        if not self.subscriptions_enabled or (private and not self.private_stream_enabled):
            raise BingXWebSocketDisabled("WebSocket subscription is disabled until its payload is reviewed")
        self._subscriptions[logical_stream] = payload
        self._handlers[logical_stream] = handler
        if self._connection is not None:
            await self._connection.send(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    async def unsubscribe(self, logical_stream: str, payload: dict[str, Any] | None = None) -> None:
        self._subscriptions.pop(logical_stream, None)
        self._handlers.pop(logical_stream, None)
        if payload is not None and self._connection is not None:
            await self._connection.send(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    async def _resubscribe(self) -> None:
        if self._connection is None:
            return
        for payload in self._subscriptions.values():
            await self._connection.send(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    def _is_duplicate(self, event: dict[str, Any]) -> bool:
        digest = hashlib.sha256(json.dumps(event, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
        if digest in self._seen:
            return True
        if len(self._seen_order) == self._seen_order.maxlen:
            self._seen.discard(self._seen_order[0])
        self._seen.add(digest)
        self._seen_order.append(digest)
        return False

    async def receive_once(self, stream_selector: Callable[[dict[str, Any]], str | None]) -> None:
        if self._connection is None:
            raise RuntimeError("WebSocket is not connected")
        event = self.decode(await self._connection.recv())
        self._last_message = self._now()
        if self._event_validator is not None and not self._event_validator(event):
            raise ValueError("WebSocket event sequence validation failed")
        if self._is_duplicate(event):
            return
        stream = stream_selector(event)
        handler = self._handlers.get(stream or "")
        if handler is not None:
            await handler(event)

    async def heartbeat(self) -> None:
        if self._heartbeat_payload is not None and self._connection is not None:
            await self._connection.send(self._heartbeat_payload)

    def stale(self) -> bool:
        return self._last_message is None or self._now() - self._last_message > self.stale_seconds

    async def reconnect(self) -> None:
        self.state = WebSocketState.RECONNECTING
        if self._connection is not None:
            await self._connection.close()
        self.reconnects += 1
        delay = min(Decimal(2) ** min(self.reconnects - 1, 10), self.max_backoff_seconds)
        delay = min(delay * (Decimal("1") + self._jitter()), self.max_backoff_seconds)
        await asyncio.sleep(float(delay))
        await self.connect()
        if self._rest_recovery is not None:
            await self._rest_recovery()

    async def run(self, stream_selector: Callable[[dict[str, Any]], str | None]) -> None:
        if self._connection is None:
            await self.connect()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self.receive_once(stream_selector), timeout=float(self.stale_seconds))
            except TimeoutError:
                await self.heartbeat()
                if self.stale():
                    await self.reconnect()
            except (ConnectionClosed, OSError, EOFError, ValueError):
                await self.reconnect()

    async def stop(self) -> None:
        self._stop.set()
        if self._connection is not None:
            await self._connection.close()
        self.state = WebSocketState.STOPPED

    def health(self) -> WebSocketHealth:
        age = self._now() - self._last_message if self._last_message is not None else None
        return WebSocketHealth(self.state, age, self.reconnects, len(self._subscriptions))

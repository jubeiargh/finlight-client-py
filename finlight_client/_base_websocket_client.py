import asyncio
import contextlib
import json
import uuid
import logging
import importlib.metadata
from websockets.asyncio.client import connect
from websockets.exceptions import (
    ConnectionClosedOK,
    ConnectionClosedError,
    InvalidStatus,
)
from typing import Callable, Optional, Type
from time import time
from pydantic import BaseModel

from .models import ApiConfig, BaseArticle

try:
    __version__ = importlib.metadata.version("finlight-client")
except Exception:
    __version__ = "unknown"

CLIENT_VERSION = f"python/finlight-client@{__version__}"


class BaseWebSocketClient:
    """Shared WebSocket connection logic for Finlight streaming endpoints.

    Subclasses must define:
        _logger_name: str          — name passed to logging.getLogger()
        _log_prefix: str           — prefix inserted into log messages (e.g. "[Raw] ")
        _article_model: Type[BaseModel] — Pydantic model used to parse sendArticle payloads

    and implement:
        _get_wss_url() -> str      — full WebSocket URL to connect to
    """

    _logger_name: str
    _log_prefix: str
    _article_model: Type[BaseArticle]
    _dedupe_articles: bool = False
    _RECENT_ARTICLE_CACHE_SIZE: int = 10

    def __init__(
        self,
        config: ApiConfig,
        ping_interval: int = 25,
        pong_timeout: int = 30,
        base_reconnect_delay: float = 0.5,
        max_reconnect_delay: float = 10.0,
        connection_lifetime: int = 115 * 60,  # 115 minutes (2h - 5m)
        on_close: Optional[Callable[[int, str], None]] = None,
        takeover: bool = False,
    ):
        self.config = config
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.base_reconnect_delay = base_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.current_reconnect_delay = base_reconnect_delay
        self.connection_lifetime = connection_lifetime
        self.on_close = on_close
        self.takeover = takeover
        self._stop = False
        self.lease_id = None
        self.connection_start_time = None
        self.reconnect_at = None
        self.client_nonce = None
        self._recent_article_links: set[str] = set()

        self._logger = logging.getLogger(self._logger_name)

    def _get_wss_url(self) -> str:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Core connection loop (called by subclass connect())
    # ------------------------------------------------------------------

    async def _connect(
        self,
        request_payload: BaseModel,
        on_article: Callable,
    ):
        p = self._log_prefix
        while not self._stop:
            try:
                self._logger.info(f"🔄 {p}Attempting to connect...")

                headers = {
                    "x-api-key": self.config.api_key,
                    "x-client-version": CLIENT_VERSION,
                }
                if self.takeover:
                    headers["x-takeover"] = "true"
                    self._logger.info(f"🔄 {p}Connecting with takeover=true")

                async with connect(
                    self._get_wss_url(),
                    additional_headers=headers,
                ) as ws:
                    self._logger.info(f"✅ {p}Connected.")

                    self._reset_backoff()
                    self.reconnect_at = None

                    self.last_pong_time = time()
                    self.connection_start_time = time()

                    self.client_nonce = str(uuid.uuid4())
                    message_data = request_payload.model_dump()
                    message_data["clientNonce"] = self.client_nonce
                    await ws.send(json.dumps(message_data))

                    tasks = [
                        asyncio.create_task(self._listen(ws, on_article)),
                        asyncio.create_task(self._ping(ws)),
                        asyncio.create_task(self._pong_watchdog(ws)),
                        asyncio.create_task(self._wait_for_close(ws)),
                        asyncio.create_task(self._proactive_rotation(ws)),
                    ]

                    _, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in pending:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

            except InvalidStatus as e:
                if e.response.status_code == 429:
                    self.reconnect_at = time() + 60
                    self._logger.warning(f"⏰ {p}Server rejected connection (429)")
                self._logger.error(
                    f"❌ {p}Connection error (status {e.response.status_code}): {e}"
                )
            except Exception as e:
                self._logger.error(f"❌ {p}Connection error: {e}")

            if not self._stop:
                await self._handle_reconnect()

    def stop(self):
        self._stop = True

    # ------------------------------------------------------------------
    # Internal tasks
    # ------------------------------------------------------------------

    async def _listen(self, ws, on_article):
        p = self._log_prefix
        try:
            async for message in ws:
                await self._handle_message(message, on_article, ws)
        except (ConnectionClosedOK, ConnectionClosedError):
            self._logger.debug(f"🔌 {p}Listen loop ended due to connection close")
        except Exception as e:
            self._logger.error(f"🔻 {p}Listen failed: {e}")

    async def _ping(self, ws):
        p = self._log_prefix
        while True:
            await asyncio.sleep(self.ping_interval)
            try:
                ping_time = int(time() * 1000)
                self._logger.debug(f"→ {p}Sending ping (t={ping_time})")
                await ws.send(json.dumps({"action": "ping", "t": ping_time}))
            except Exception as e:
                self._logger.error(f"❌ {p}Ping send error: {e}")
                try:
                    await ws.close()
                except:
                    pass
                raise ConnectionError("Ping failed, triggering reconnect") from e

    async def _pong_watchdog(self, ws):
        p = self._log_prefix
        while True:
            await asyncio.sleep(5)
            if time() - self.last_pong_time > self.pong_timeout:
                self._logger.warning(
                    f"❌ {p}No pong received in time — forcing reconnect."
                )
                await ws.close()
                break

    async def _wait_for_close(self, ws):
        p = self._log_prefix
        try:
            await ws.wait_closed()

            close_code = ws.close_code or 1000
            close_reason = ws.close_reason or "Connection closed"
            self._logger.info(f"🔌 {p}Connection closed: {close_code} - {close_reason}")

            if self.on_close:
                try:
                    self.on_close(close_code, close_reason)
                except Exception as callback_error:
                    self._logger.error(f"❌ {p}Close callback error: {callback_error}")

            if close_code == 1008:
                self._logger.warning(
                    f"🚫 {p}Connection rejected by server (blocked user)"
                )
                self._stop = True
            elif close_code == 1013:
                self._logger.warning(f"⏰ {p}Rate limited, waiting before reconnect...")
            elif close_code == 4001:
                self._logger.warning(f"⏰ {p}Rate limited - custom close code")
            elif close_code == 4002:
                self._logger.warning(f"🚫 {p}User blocked - custom close code")
            elif close_code == 4003:
                self._logger.warning(f"👮 {p}Admin kick - custom close code")

        except Exception as e:
            self._logger.error(f"❌ {p}Error waiting for close: {e}")

    async def _proactive_rotation(self, ws):
        p = self._log_prefix
        try:
            await asyncio.sleep(self.connection_lifetime)

            connection_age = time() - (self.connection_start_time or time())
            self._logger.info(
                f"🔄 {p}Proactive rotation after {connection_age/60:.1f} minutes (before 2h AWS limit)"
            )
            await ws.close(code=4000, reason="Proactive rotation")

        except Exception as e:
            self._logger.error(f"❌ {p}Error in proactive rotation: {e}")

    # ------------------------------------------------------------------
    # Reconnect / backoff
    # ------------------------------------------------------------------

    async def _handle_reconnect(self):
        p = self._log_prefix
        now = time()

        if self.reconnect_at and now < self.reconnect_at:
            wait_time = self.reconnect_at - now
            self._logger.info(
                f"⏰ {p}Waiting {wait_time:.1f}s until reconnectAt before attempting reconnect"
            )
            await asyncio.sleep(wait_time)
        else:
            self._logger.info(
                f"🔁 {p}Reconnecting in {self.current_reconnect_delay:.1f}s..."
            )
            await asyncio.sleep(self.current_reconnect_delay)
            self.current_reconnect_delay = min(
                self.current_reconnect_delay * 2, self.max_reconnect_delay
            )

    def _reset_backoff(self):
        self.current_reconnect_delay = self.base_reconnect_delay

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def _handle_message(self, message: str, on_article, ws):
        p = self._log_prefix
        try:
            msg = json.loads(message)
            msg_action = msg.get("action")

            if msg_action == "pong":
                ping_time = msg.get("t")
                if ping_time:
                    rtt = int(time() * 1000) - ping_time
                    self._logger.debug(f"← {p}PONG received (RTT: {rtt}ms)")
                else:
                    self._logger.debug(f"← {p}PONG received")
                self.last_pong_time = time()

            elif msg_action == "admit":
                self.lease_id = msg.get("leaseId")
                server_now = msg.get("serverNow")
                client_nonce = msg.get("clientNonce")
                self._logger.info(
                    f"✅ {p}Admitted (leaseId: {self.lease_id}, serverNow: {server_now})"
                )
                if client_nonce and client_nonce != self.client_nonce:
                    self._logger.warning(
                        f"⚠️ {p}Nonce mismatch: expected {self.client_nonce}, got {client_nonce}"
                    )

            elif msg_action == "preempted":
                reason = msg.get("reason", "unknown")
                new_lease_id = msg.get("newLeaseId", "")
                self._logger.warning(
                    f"🔄 {p}Connection preempted: {reason} (new lease: {new_lease_id})"
                )
                self._stop = True
                await ws.close(code=1000, reason="Preempted by server")

            elif msg_action == "sendArticle":
                data = msg.get("data", {})
                article = self._article_model.model_validate(data)

                if self._dedupe_articles:
                    if article.link in self._recent_article_links:
                        self._logger.debug(f"⏭️ {p}Skipping duplicate article: {article.link}")
                        return

                    self._recent_article_links.add(article.link)
                    if len(self._recent_article_links) > self._RECENT_ARTICLE_CACHE_SIZE:
                        self._recent_article_links.pop()

                on_article(article)

            elif msg_action == "admin_kick":
                retry_after = msg.get("retryAfter", 900000)  # 15 minutes default
                retry_after_seconds = retry_after / 1000
                self.reconnect_at = time() + retry_after_seconds
                self._logger.warning(
                    f"🚫 {p}Admin kicked - retry after {retry_after_seconds:.0f}s"
                )
                await ws.close(
                    code=4003, reason=f"Admin kick - retry after {retry_after}ms"
                )

            elif msg_action == "error":
                error_data = msg.get("data") or msg.get("error", "Unknown error")
                self._logger.error(f"❌ {p}Server error: {error_data}")

                if "limit" in str(error_data).lower():
                    self.reconnect_at = time() + 60
                    await ws.close(code=4001, reason="Rate limited")
                elif "blocked" in str(error_data).lower():
                    self.reconnect_at = time() + 3600
                    await ws.close(code=4002, reason="User blocked")

            else:
                self._logger.warning(f"⚠️ {p}Unknown message action: {msg_action}")
                self._logger.debug(msg)

        except Exception as e:
            self._logger.error(f"❌ {p}Error handling message: {e}")
            self._logger.debug(f"Raw message: {message}")

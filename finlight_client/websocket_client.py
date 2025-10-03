import asyncio
import contextlib
import json
from websockets.client import connect
from websockets.exceptions import (
    ConnectionClosedOK,
    ConnectionClosedError,
    InvalidStatusCode,
)

from typing import Callable, Optional
from time import time
from .models import ApiConfig, Article, GetArticlesWebSocketParams
import logging
import importlib.metadata

logger = logging.getLogger("finlight-websocket-client")
logger.setLevel(logging.DEBUG)

try:
    __version__ = importlib.metadata.version("finlight-client")
except Exception:
    __version__ = "unknown"

CLIENT_VERSION = f"python/finlight-client@{__version__}"


class WebSocketClient:
    def __init__(
        self,
        config: ApiConfig,
        ping_interval: int = 25,  # 25 seconds (matches HEARTBEAT_MS)
        pong_timeout: int = 30,
        base_reconnect_delay: float = 0.5,  # Start with 500ms
        max_reconnect_delay: float = 10.0,  # Cap at 10 seconds
        connection_lifetime: int = 115 * 60,  # 115 minutes (2h - 5m)
        on_close: Optional[Callable[[int, str], None]] = None,
        takeover: bool = False,  # Whether to takeover existing connections
    ):
        self.config = config
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.base_reconnect_delay = base_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.current_reconnect_delay = base_reconnect_delay
        self.connection_lifetime = connection_lifetime
        self.on_close = on_close  # Callback for close events
        self.takeover = takeover  # Whether to takeover existing connections
        self._stop = False
        self.lease_id = None  # Store lease ID from admission
        self.connection_start_time = None  # Track when connection started
        self.reconnect_at = (
            None  # Timestamp when we can reconnect (for rate limits/blocks)
        )
        self.client_nonce = None  # For idempotent handshake

    async def connect(
        self,
        request_payload: GetArticlesWebSocketParams,
        on_article: Callable[[Article], None],
    ):
        while not self._stop:
            try:
                logger.info("🔄 Attempting to connect...")

                # Prepare headers
                headers = {
                    "x-api-key": self.config.api_key,
                    "x-client-version": CLIENT_VERSION,
                }
                if self.takeover:
                    headers["x-takeover"] = "true"
                    logger.info("🔄 Connecting with takeover=true")

                async with connect(
                    self.config.wss_url,
                    extra_headers=headers,
                ) as ws:
                    logger.info("✅ Connected.")

                    # Reset backoff on successful connection
                    self._reset_backoff()
                    self.reconnect_at = None  # Clear any reconnectAt restriction

                    self.last_pong_time = time()
                    self.connection_start_time = time()  # Track connection start

                    listen_task = asyncio.create_task(self._listen(ws, on_article))
                    ping_task = asyncio.create_task(self._ping(ws))
                    watchdog_task = asyncio.create_task(self._pong_watchdog(ws))
                    close_task = asyncio.create_task(self._wait_for_close(ws))
                    rotation_task = asyncio.create_task(self._proactive_rotation(ws))

                    # Prepare first message with handshake fields
                    import uuid

                    self.client_nonce = str(uuid.uuid4())

                    # Create message with handshake fields
                    message_data = request_payload.model_dump()
                    message_data["clientNonce"] = self.client_nonce

                    # Send article search request to $default route
                    await ws.send(json.dumps(message_data))

                    # Wait for any task to complete (including close detection and proactive rotation)
                    _, pending = await asyncio.wait(
                        [
                            listen_task,
                            ping_task,
                            watchdog_task,
                            close_task,
                            rotation_task,
                        ],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # Cancel the others safely
                    for task in pending:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

            except InvalidStatusCode as e:
                # Handle 429 responses - API Gateway WebSocket doesn't pass custom headers
                if e.status_code == 429:
                    # Use fixed delay for 429 responses since we can't get server retry timing
                    retry_after_seconds = 60  # Fixed 1 minute delay for capacity limits
                    self.reconnect_at = time() + retry_after_seconds
                    logger.warning(f"⏰ Server rejected connection (429)")

                logger.error(f"❌ Connection error (status {e.status_code}): {e}")
            except Exception as e:
                logger.error(f"❌ Connection error: {e}")

            if not self._stop:
                await self._handle_reconnect()

    async def _listen(self, ws, on_article):
        try:
            async for message in ws:
                await self._handle_message(message, on_article, ws)
        except (ConnectionClosedOK, ConnectionClosedError):
            # Close is now handled by _wait_for_close task
            logger.debug("🔌 Listen loop ended due to connection close")
        except Exception as e:
            logger.error(f"🔻 Listen failed: {e}")

    async def _ping(self, ws):
        while True:
            await asyncio.sleep(self.ping_interval)
            try:
                ping_time = int(time() * 1000)  # milliseconds
                logger.debug(f"→ Sending ping (t={ping_time})")
                await ws.send(json.dumps({"action": "ping", "t": ping_time}))
            except Exception as e:
                logger.error(f"❌ Ping send error: {e}")
                try:
                    await ws.close()
                except:
                    pass
                raise ConnectionError("Ping failed, triggering reconnect") from e

    async def _pong_watchdog(self, ws):
        while True:
            await asyncio.sleep(5)
            if time() - self.last_pong_time > self.pong_timeout:
                logger.warning("❌ No pong received in time — forcing reconnect.")
                await ws.close()
                break  # Exit watchdog to trigger reconnect

    async def _wait_for_close(self, ws):
        """Wait for connection to close and handle the close event"""
        try:
            await ws.wait_closed()

            close_code = ws.close_code or 1000
            close_reason = ws.close_reason or "Connection closed"
            logger.info(f"🔌 Connection closed: {close_code} - {close_reason}")

            if self.on_close:
                try:
                    self.on_close(close_code, close_reason)
                except Exception as callback_error:
                    logger.error(f"❌ Close callback error: {callback_error}")

            # Handle specific close codes for reconnection logic
            if close_code == 1008:  # Policy violation (blocked user)
                logger.warning("🚫 Connection rejected by server (blocked user)")
                self._stop = True  # Stop reconnecting
            elif close_code == 1013:  # Try again later (rate limited)
                logger.warning("⏰ Rate limited, waiting before reconnect...")
                # The main loop will handle reconnect delay
            elif close_code == 4001:  # Custom: Rate limited
                logger.warning("⏰ Rate limited - custom close code")
            elif close_code == 4002:  # Custom: User blocked
                logger.warning("🚫 User blocked - custom close code")
            elif close_code == 4003:  # Custom: Admin kick
                logger.warning("👮 Admin kick - custom close code")

        except Exception as e:
            logger.error(f"❌ Error waiting for close: {e}")

    async def _proactive_rotation(self, ws):
        """Proactively close connection before AWS 2-hour limit"""
        try:
            # Wait for connection lifetime (115 minutes = 2h - 5m)
            await asyncio.sleep(self.connection_lifetime)

            connection_age = time() - (self.connection_start_time or time())
            logger.info(
                f"🔄 Proactive rotation after {connection_age/60:.1f} minutes (before 2h AWS limit)"
            )

            # Gracefully close the connection with custom code
            await ws.close(code=4000, reason="Proactive rotation")

        except Exception as e:
            logger.error(f"❌ Error in proactive rotation: {e}")

    async def _handle_reconnect(self):
        """Handle reconnection with exponential backoff and reconnectAt respect"""
        now = time()

        # Check if we need to wait due to rate limits/blocks
        if self.reconnect_at and now < self.reconnect_at:
            wait_time = self.reconnect_at - now
            logger.info(
                f"⏰ Waiting {wait_time:.1f}s until reconnectAt before attempting reconnect"
            )
            await asyncio.sleep(wait_time)
        else:
            # Regular exponential backoff
            logger.info(f"🔁 Reconnecting in {self.current_reconnect_delay:.1f}s...")
            await asyncio.sleep(self.current_reconnect_delay)

            # Increase delay for next time (exponential backoff)
            self.current_reconnect_delay = min(
                self.current_reconnect_delay * 2, self.max_reconnect_delay
            )

    def _reset_backoff(self):
        """Reset exponential backoff on successful connection"""
        self.current_reconnect_delay = self.base_reconnect_delay

    async def _handle_message(self, message: str, on_article, ws):
        try:
            msg = json.loads(message)
            msg_action = msg.get("action")

            if msg_action == "pong":
                ping_time = msg.get("t")
                if ping_time:
                    rtt = int(time() * 1000) - ping_time
                    logger.debug(f"← PONG received (RTT: {rtt}ms)")
                else:
                    logger.debug("← PONG received")
                self.last_pong_time = time()

            elif msg_action == "admit":
                self.lease_id = msg.get("leaseId")
                server_now = msg.get("serverNow")
                client_nonce = msg.get("clientNonce")
                logger.info(
                    f"✅ Admitted (leaseId: {self.lease_id}, serverNow: {server_now})"
                )
                if client_nonce and client_nonce != self.client_nonce:
                    logger.warning(
                        f"⚠️ Nonce mismatch: expected {self.client_nonce}, got {client_nonce}"
                    )

            elif msg_action == "preempted":
                reason = msg.get("reason", "unknown")
                new_lease_id = msg.get("newLeaseId", "")
                logger.warning(
                    f"🔄 Connection preempted: {reason} (new lease: {new_lease_id})"
                )
                # Stop reconnecting - this connection was legitimately replaced
                self._stop = True
                await ws.close(code=1000, reason="Preempted by server")

            elif msg_action == "sendArticle":
                data = msg.get("data", {})
                article = Article.model_validate(data)
                on_article(article)

            elif msg_action == "admin_kick":
                retry_after = msg.get("retryAfter", 900000)  # 15 minutes default
                retry_after_seconds = retry_after / 1000
                self.reconnect_at = time() + retry_after_seconds
                logger.warning(
                    f"🚫 Admin kicked - retry after {retry_after_seconds:.0f}s"
                )
                # Close with custom code and let reconnect logic handle the delay
                await ws.close(
                    code=4003, reason=f"Admin kick - retry after {retry_after}ms"
                )

            elif msg_action == "error":
                error_data = msg.get("data") or msg.get("error", "Unknown error")
                logger.error(f"❌ Server error: {error_data}")

                # Check if it's a rate limit or blocked error
                if "limit" in str(error_data).lower():
                    # Set reconnectAt for rate limits
                    self.reconnect_at = time() + 60  # Wait 1 minute for rate limits
                    await ws.close(code=4001, reason="Rate limited")
                elif "blocked" in str(error_data).lower():
                    # Set reconnectAt for blocked users
                    self.reconnect_at = time() + 3600  # Wait 1 hour for blocks
                    await ws.close(code=4002, reason="User blocked")

            else:
                logger.warning(f"⚠️ Unknown message action: {msg_action}")
                logger.debug(msg)

        except Exception as e:
            logger.error(f"❌ Error handling message: {e}")
            logger.debug(f"Raw message: {message}")

    def stop(self):
        self._stop = True

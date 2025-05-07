import asyncio
import contextlib
import json
from websockets.client import connect
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

from typing import Callable, Union
from time import time
from .models import ApiConfig, BasicArticle, Article, GetArticlesWebSocketParams
import logging

logger = logging.getLogger("finlight-websocket-client")
logger.setLevel(logging.DEBUG)


class WebSocketClient:
    def __init__(
        self,
        config: ApiConfig,
        ping_interval: int = 30,  # 30 seconds
        pong_timeout: int = 60,
        reconnect_delay: int = 1,
    ):
        self.config = config
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.reconnect_delay = reconnect_delay
        self._stop = False

    async def connect(
        self,
        request_payload: GetArticlesWebSocketParams,
        on_article: Callable[[Union[BasicArticle, Article]], None],
    ):
        while not self._stop:
            try:
                logger.info("🔄 Attempting to connect...")
                async with connect(
                    self.config.wss_url,
                    extra_headers={"x-api-key": self.config.api_key},
                ) as ws:
                    logger.info("✅ Connected.")

                    self.last_pong_time = time()

                    listen_task = asyncio.create_task(self._listen(ws, on_article))
                    ping_task = asyncio.create_task(self._ping(ws))
                    watchdog_task = asyncio.create_task(self._pong_watchdog(ws))

                    await ws.send(request_payload.model_dump_json())

                    # Wait for either task to complete (or crash)
                    done, pending = await asyncio.wait(
                        [listen_task, ping_task, watchdog_task],
                        return_when=asyncio.FIRST_EXCEPTION,
                    )

                    # Cancel the others safely
                    for task in pending:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task
            except Exception as e:
                logger.error(f"❌ Connection error: {e}")

            if not self._stop:
                logger.info(f"🔁 Reconnecting in {self.reconnect_delay} seconds...")
                await asyncio.sleep(self.reconnect_delay)

    async def _listen(self, ws, on_article):
        try:
            async for message in ws:
                await self._handle_message(message, on_article)
        except (ConnectionClosedOK, ConnectionClosedError):
            logger.warning("🔌 Server closed the connection.")
        except Exception as e:
            logger.error(f"🔻 Listen failed: {e}")

    async def _ping(self, ws):
        while True:
            await asyncio.sleep(self.ping_interval)
            try:
                print("→ Sending ping")
                await ws.send(json.dumps({"action": "ping"}))
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

    async def _handle_message(self, message: str, on_article):
        try:
            msg = json.loads(message)
            action = msg.get("action")

            if action == "pong":
                print("← PONG received")
                self.last_pong_time = time()
            elif action == "sendArticle":
                data = msg.get("data", {})
                article = Article.model_validate(data)
                on_article(article)
            else:
                logger.warning(f"⚠️ Unknown action: {action}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def stop(self):
        self._stop = True

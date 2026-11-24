"""A webhook endpoint with the standard library only.

* Read the raw body bytes and verify them before parsing anything.
* Answer 2xx quickly (within 5 s) and do slow work afterwards, here in a worker thread.
* Deduplicate on event_id: deliveries are at-least-once.
* Answer a WrongPayloadVersion (a v2 body, for example a retry sent before you
  switched the webhook to v3) with 2xx too, and keep its raw JSON if you need it.
* Never answer 410: it disables the webhook at once.
"""

from __future__ import annotations

import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from finlight_client import (
    FinlightDecodeError,
    WebhookEvent,
    Webhooks,
    WebhookVerificationError,
    WrongPayloadVersion,
)

SECRET = os.environ.get("FINLIGHT_WEBHOOK_SECRET", "")
seen_event_ids: set[str] = set()  # use a shared store (database, Redis) in production
work: queue.Queue[Any] = queue.Queue()


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server API
        raw_body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            result = Webhooks.construct_event(raw_body, self.headers, SECRET)
        except (WebhookVerificationError, FinlightDecodeError):
            self.answer(400)
            return
        if isinstance(result, WrongPayloadVersion):
            work.put(("legacy", result.raw))  # keep it; answer 2xx so the webhook stays enabled
        elif isinstance(result, WebhookEvent) and result.event_id not in seen_event_ids:
            seen_event_ids.add(result.event_id)
            work.put(("event", result))
        self.answer(204)

    def answer(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


def process(kind: str, item: Any) -> None:
    if kind == "event":
        print(item.event, item.event_id, "test" if item.is_test else "", item.data.title)
    else:
        print("legacy body for", item.get("link"))


def worker() -> None:
    while True:
        kind, item = work.get()
        process(kind, item)
        work.task_done()


def make_server(port: int = 8080) -> ThreadingHTTPServer:
    threading.Thread(target=worker, daemon=True).start()
    return ThreadingHTTPServer(("127.0.0.1", port), WebhookHandler)


def main() -> None:
    server = make_server(int(os.environ.get("PORT", "8080")))
    print("listening on", server.server_address)
    server.serve_forever()


if __name__ == "__main__":
    main()

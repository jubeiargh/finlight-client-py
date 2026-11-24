"""Stream articles in real time (async)."""

from __future__ import annotations

import asyncio
from typing import Optional

from _env import client_options

from finlight_client import FinlightClient


def on_reconnect(last_seen: Optional[str], reason: str) -> None:
    # No automatic backfill: fill the gap yourself, for example with
    # client.articles.search_all(from_=last_seen, order_by="availableAt", ...).
    print(f"reconnected ({reason}); last seen {last_seen}")


async def main(max_events: Optional[int] = None) -> None:
    client = FinlightClient(**client_options())
    count = 0
    async with client.stream(
        query="ticker:NVDA",
        language="en",
        include=["companies", "events"],
        include_updates=True,
        on_reconnect=on_reconnect,
        on_error=lambda error: print("stream problem (still running):", error),
    ) as stream:
        async for event in stream:
            if event.data is None:
                print("other event:", event.event)  # a future event type, kept as is
                continue
            print(event.kind, event.data.id, event.data.title)
            count += 1
            if max_events is not None and count >= max_events:
                break
    client.close()


if __name__ == "__main__":
    asyncio.run(main())

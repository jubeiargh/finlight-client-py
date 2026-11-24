"""Stream articles in real time (async). Stops after 5 articles."""

from __future__ import annotations

import asyncio

from _env import client_options

from finlight_client import (
    AdmittedInfo,
    FinlightApiError,
    FinlightClient,
    FinlightError,
    PreemptedError,
    QuotaWaitInfo,
    ReconnectInfo,
)


def on_admitted(info: AdmittedInfo) -> None:
    # Arrives before the server checks the subscribe; it does not mean it was accepted.
    print("admitted, lease", info.lease_id)


def on_reconnect(info: ReconnectInfo) -> None:
    # No automatic backfill: fill the gap yourself if you need it, for example with
    # client.articles.search_all(from_=info.last_seen_at, order_by="availableAt", ...).
    print(f"reconnected ({info.reason}, connection {info.connection}); last seen {info.last_seen_at}")


def on_error(error: FinlightError) -> None:
    print("stream problem (still running):", error)


def on_quota_wait(info: QuotaWaitInfo) -> None:
    print(f"WebSocket quota used up; next try in {info.next_attempt_in:.0f} s")


async def main(max_events: int = 5) -> None:
    client = FinlightClient(**client_options())
    count = 0
    try:
        async with client.stream(
            query="ticker:NVDA",
            include=["companies"],
            include_updates=True,
            on_admitted=on_admitted,
            on_reconnect=on_reconnect,
            on_error=on_error,
            on_quota_wait=on_quota_wait,
        ) as stream:
            async for event in stream:
                if event.kind == "other" or event.data is None:
                    continue  # an event this SDK does not know yet
                print(event.kind, event.data.id, event.data.title)
                count += 1
                if count >= max_events:
                    break
    except PreemptedError as error:
        print("another connection took over:", error.reason, error.new_lease_id)
    except FinlightApiError as error:
        print("stream ended:", error.api_kind, error.status, error.detail)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())

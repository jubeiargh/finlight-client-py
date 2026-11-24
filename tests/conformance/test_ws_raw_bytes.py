"""S-02: the dial request carries exactly ``x-api-key`` (lowercase), never the key in the URL.

A plain TCP listener reads the raw upgrade request bytes; nothing normalizes header case.
"""

from __future__ import annotations

import asyncio

import pytest

from finlight_client import FinlightClient, UnauthorizedError, __version__
from tests.support import KIT_KEY


async def capture_dial(raw: bool, takeover: bool = False) -> bytes:
    received: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        data = await reader.readuntil(b"\r\n\r\n")
        if not received.done():
            received.set_result(data)
        body = b'{"message":"Invalid API key"}'
        writer.write(
            b"HTTP/1.1 401 Unauthorized\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        client = FinlightClient(api_key=KIT_KEY, wss_url=f"ws://127.0.0.1:{port}", takeover=takeover)
        stream = client.raw_stream(query="x") if raw else client.stream(query="x")
        with pytest.raises(UnauthorizedError) as info:
            async for _ in stream:
                pass
        assert info.value.status == 401 and info.value.detail == "Invalid API key"
        return await asyncio.wait_for(received, 3)
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.parametrize("case", ["S-02"])
async def test_lowercase_api_key_on_the_wire(case: str) -> None:
    data = await capture_dial(raw=False)
    request_line, _, rest = data.partition(b"\r\n")
    assert request_line == b"GET / HTTP/1.1"
    assert b"apikey" not in request_line.lower() and KIT_KEY.encode() not in request_line
    lines = rest.split(b"\r\n")
    assert b"x-api-key: " + KIT_KEY.encode() in lines
    assert not any(line.lower().startswith(b"x-api-key:") and not line.startswith(b"x-api-key:") for line in lines)
    assert b"x-client-version: " + __version__.encode() in lines
    assert b"User-Agent: finlight-client-python/" + __version__.encode() in lines
    assert not any(line.lower().startswith(b"x-takeover") for line in lines)


async def test_raw_endpoint_and_takeover_header() -> None:
    data = await capture_dial(raw=True, takeover=True)
    assert data.startswith(b"GET /raw HTTP/1.1\r\n")
    assert b"\r\nx-takeover: true\r\n" in data
    assert b"\r\nx-api-key: " in data

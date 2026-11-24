"""Shared settings for the examples: the key and optional URLs come from the environment."""

from __future__ import annotations

import os
from typing import Any


def client_options() -> dict[str, Any]:
    options: dict[str, Any] = {"api_key": os.environ["FINLIGHT_API_KEY"]}
    if os.environ.get("FINLIGHT_BASE_URL"):
        options["base_url"] = os.environ["FINLIGHT_BASE_URL"]
    if os.environ.get("FINLIGHT_WSS_URL"):
        options["wss_url"] = os.environ["FINLIGHT_WSS_URL"]
    return options

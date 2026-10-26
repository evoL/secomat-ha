"""Minimal async client for the Krüger Secomat cloud API.

Reverse-engineered from the official "secomat" Android app (ch.krueger.secomat).
Single resource, two verbs:
  GET  {base}/plc  -> current device state
  POST {base}/plc  -> send a command
Both authenticated with two headers: `claim-token` (per-device secret obtained once
via the app's own BLE pairing/claim flow) and `api` (constant, "1").
"""
from __future__ import annotations

from typing import Any

import aiohttp

from .const import DEFAULT_API_BASE_URL


class SecomatApiError(Exception):
    """Raised when the Secomat API returns an error or is unreachable."""


class SecomatAuthError(SecomatApiError):
    """Raised when the cloud API rejects the Claim Token."""


class SecomatClient:
    """Talks to a single claimed Secomat device via the Krüger cloud API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        claim_token: str,
        base_url: str = DEFAULT_API_BASE_URL,
    ) -> None:
        self._session = session
        self._token = claim_token
        self._base_url = base_url.rstrip("/") + "/"

    @property
    def _headers(self) -> dict[str, str]:
        # "Connection: close" forces aiohttp to drop the underlying TCP connection
        # after each response instead of returning it to the shared session's pool.
        # We only poll every 30 seconds, so there's no real cost to this - but it avoids
        # a real failure mode: a brief network blip can leave a pooled keep-alive
        # connection silently broken, and aiohttp will keep handing it back out
        # (raising "Network unreachable" every poll) until something evicts it. Without
        # this, the only fix was restarting Home Assistant.
        return {"claim-token": self._token, "api": "1", "Connection": "close"}

    async def async_get_state(self) -> dict[str, Any]:
        """Fetch a normalized state envelope containing src, age, and payload."""
        url = self._base_url + "plc"
        try:
            async with self._session.get(
                url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status in (401, 403):
                    raise SecomatAuthError(f"GET plc failed: HTTP {resp.status}")
                if resp.status != 200:
                    text = await resp.text()
                    raise SecomatApiError(f"GET plc failed: HTTP {resp.status}: {text}")
                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SecomatApiError(f"GET plc failed: {err}") from err
        return {
            "src": data.get("src"),
            "age": data.get("age"),
            "payload": data.get("payload", {}),
        }

    async def async_send_command(
        self, command: str, args: dict[str, int] | None = None
    ) -> None:
        """Send a command, e.g. OFF / WASH_AUTO / WASH_MANUAL_ON / ROOM_ON / ROOM_OFF /
        CHANGE (with args like {"hmi_backlight": 1})."""
        url = self._base_url + "plc"
        body = {"command": command, "args": args or {}}
        try:
            async with self._session.post(
                url,
                headers=self._headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (401, 403):
                    raise SecomatAuthError(f"POST plc failed: HTTP {resp.status}")
                if resp.status not in (200, 204):
                    text = await resp.text()
                    raise SecomatApiError(
                        f"POST plc {command} failed: HTTP {resp.status}: {text}"
                    )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SecomatApiError(f"POST plc {command} failed: {err}") from err

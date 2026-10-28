"""Polling and shared device metadata for one Secomat."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SecomatApiError, SecomatAuthError, SecomatClient
from .const import (
    ARG_WASH_START_TIME,
    CMD_WASH_MANUAL_OFF,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    POWER_MODE_ON,
    POWER_MODE_READY,
    POWER_MODE_TO_COMMAND,
)

_LOGGER = logging.getLogger(__name__)


class SecomatCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll a Secomat and distinguish rejected Claim Tokens from outages."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SecomatClient,
        secomat_id: str,
        name: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"secomat_{secomat_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.secomat_id = secomat_id
        self.device_name = name

    @property
    def payload(self) -> dict[str, Any]:
        """The latest Secomat state without the cloud transport envelope."""
        return self.data.get("payload", {})

    @property
    def is_secomat_connected(self) -> bool:
        """Whether the cloud has a live WebSocket connection to the Secomat."""
        return self.data.get("src") == "ws"

    @property
    def device_info(self) -> DeviceInfo:
        """Link every entity to the same Secomat in the Device Registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.secomat_id)},
            name=self.device_name,
            manufacturer="Krüger + Co. AG",
            model="Secomat",
            serial_number=self.secomat_id,
            sw_version=self.payload.get("fw_version"),
        )

    async def async_set_power_mode(self, mode: int) -> None:
        """Choose the command for the transition, not just the requested Power Mode."""
        command = POWER_MODE_TO_COMMAND[mode]
        if mode == POWER_MODE_READY and self.payload.get("operating_mode") == POWER_MODE_ON:
            # WASH_AUTO arms Auto from Off; active laundry drying must be stopped instead.
            command = CMD_WASH_MANUAL_OFF
        args = {ARG_WASH_START_TIME: 0} if mode == POWER_MODE_ON else None
        await self.async_send_command(command, args)

    async def async_send_command(
        self, command: str, args: dict[str, int] | None = None
    ) -> None:
        """Send a command and allow the Secomat to report its new state before refreshing."""
        try:
            await self.client.async_send_command(command, args)
        except SecomatAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError("The Secomat Claim Token was rejected") from err
        except SecomatApiError as err:
            raise HomeAssistantError(f"Failed to send Secomat command {command}: {err}") from err
        await asyncio.sleep(2)
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.async_get_state()
        except SecomatAuthError as err:
            raise ConfigEntryAuthFailed("The Secomat Claim Token was rejected") from err
        except SecomatApiError as err:
            raise UpdateFailed(str(err)) from err

        # Entity device_info is read at registration, not on subsequent state updates.
        firmware = data.get("payload", {}).get("fw_version")
        registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(registry, self.config_entry.entry_id):
            if device.sw_version != firmware:
                registry.async_update_device(device.id, sw_version=firmware)
        return data


type SecomatConfigEntry = ConfigEntry[SecomatCoordinator]

"""Polling and shared device metadata for one Secomat."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SecomatApiError, SecomatAuthError, SecomatClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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
            sw_version=self.data.get("payload", {}).get("fw_version"),
        )

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

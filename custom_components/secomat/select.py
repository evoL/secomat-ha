"""Select entity for the Secomat's Power Mode."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import SecomatApiError
from .const import POWER_MODE_NAMES, POWER_MODE_TO_COMMAND
from .coordinator import SecomatConfigEntry, SecomatCoordinator
from .entity import SecomatEntity

_LOGGER = logging.getLogger(__name__)

NAME_TO_MODE = {v: k for k, v in POWER_MODE_NAMES.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: SecomatConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SecomatPowerModeSelect(entry.runtime_data)])


class SecomatPowerModeSelect(SecomatEntity, SelectEntity):
    _attr_name = "Power mode"
    _attr_icon = "mdi:tumble-dryer"
    _attr_options = list(POWER_MODE_NAMES.values())

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_power_mode"

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.data.get("payload", {}).get("operating_mode")
        return POWER_MODE_NAMES.get(mode)

    async def async_select_option(self, option: str) -> None:
        mode = NAME_TO_MODE.get(option)
        if mode is None:
            _LOGGER.error("Unknown secomat power mode option: %s", option)
            return
        command = POWER_MODE_TO_COMMAND[mode]
        try:
            await self.coordinator.client.async_send_command(command)
        except SecomatApiError as err:
            _LOGGER.error("Failed to set secomat power mode to %s: %s", option, err)
            return
        await self.coordinator.async_request_refresh()

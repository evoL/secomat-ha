"""Select entity for the Secomat's power/operating mode."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SecomatCoordinator
from .api import SecomatApiError
from .const import DOMAIN, POWER_MODE_NAMES, POWER_MODE_TO_COMMAND

_LOGGER = logging.getLogger(__name__)

NAME_TO_MODE = {v: k for k, v in POWER_MODE_NAMES.items()}


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities: AddEntitiesCallback, discovery_info=None
) -> None:
    if discovery_info is None:
        return
    entities = [
        SecomatPowerModeSelect(coordinator)
        for coordinator in hass.data.get(DOMAIN, {}).values()
    ]
    async_add_entities(entities)


class SecomatPowerModeSelect(CoordinatorEntity[SecomatCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Secomat power mode"
    _attr_icon = "mdi:tumble-dryer"
    _attr_options = list(POWER_MODE_NAMES.values())

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_power_mode"

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.data.get("operating_mode")
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

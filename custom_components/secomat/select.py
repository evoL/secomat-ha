"""Select entities for Power Mode and Target Humidity Level."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ARG_WASH_RESIDUAL_MOISTURE_TARGET,
    ARG_WASH_START_TIME,
    CMD_CHANGE,
    POWER_MODE_NAMES,
    POWER_MODE_ON,
    POWER_MODE_TO_COMMAND,
)
from .coordinator import SecomatConfigEntry, SecomatCoordinator
from .entity import SecomatEntity

_LOGGER = logging.getLogger(__name__)

NAME_TO_MODE = {v: k for k, v in POWER_MODE_NAMES.items()}
TARGET_HUMIDITY_NAMES = {0: "Very dry", 1: "Dry", 2: "Medium", 3: "Humid"}
NAME_TO_TARGET_HUMIDITY = {v: k for k, v in TARGET_HUMIDITY_NAMES.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: SecomatConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [SecomatPowerModeSelect(coordinator), SecomatTargetHumiditySelect(coordinator)]
    )


class SecomatPowerModeSelect(SecomatEntity, SelectEntity):
    _attr_name = "Power mode"
    _attr_icon = "mdi:tumble-dryer"
    _attr_options = list(POWER_MODE_NAMES.values())

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_power_mode"

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.payload.get("operating_mode")
        return POWER_MODE_NAMES.get(mode)

    async def async_select_option(self, option: str) -> None:
        mode = NAME_TO_MODE.get(option)
        if mode is None:
            _LOGGER.error("Unknown secomat power mode option: %s", option)
            return
        command = POWER_MODE_TO_COMMAND[mode]
        args = {ARG_WASH_START_TIME: 0} if mode == POWER_MODE_ON else None
        await self.coordinator.async_send_command(command, args)


class SecomatTargetHumiditySelect(SecomatEntity, SelectEntity):
    """The desired residual moisture level at the end of a drying cycle."""

    _attr_name = "Target humidity level"
    _attr_options = list(TARGET_HUMIDITY_NAMES.values())

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_target_humidity_level"

    @property
    def current_option(self) -> str | None:
        level = self.coordinator.payload.get("target_humidity_level")
        return TARGET_HUMIDITY_NAMES.get(level)

    async def async_select_option(self, option: str) -> None:
        level = NAME_TO_TARGET_HUMIDITY[option]
        await self.coordinator.async_send_command(
            CMD_CHANGE, {ARG_WASH_RESIDUAL_MOISTURE_TARGET: level}
        )

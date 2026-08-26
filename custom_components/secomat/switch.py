"""Switch entity for the Secomat's 24h room-drying mode."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SecomatCoordinator
from .api import SecomatApiError
from .const import (
    CMD_OFF,
    CMD_ROOM_OFF,
    CMD_ROOM_ON,
    CMD_WASH_AUTO,
    DOMAIN,
    POWER_MODE_READY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities: AddEntitiesCallback, discovery_info=None
) -> None:
    if discovery_info is None:
        return
    entities = []
    for coordinator in hass.data.get(DOMAIN, {}).values():
        entities.append(SecomatAutoDrySwitch(coordinator))
        entities.append(SecomatRoomDryingSwitch(coordinator))
    async_add_entities(entities)


class SecomatAutoDrySwitch(CoordinatorEntity[SecomatCoordinator], SwitchEntity):
    """One-tap control for the secomat's 'Auto' drying mode (READY).

    On = Auto (the app's smart start-stop mode: waits for laundry, dries it
    automatically). Off = Off (STAND_BY). Doesn't touch "Manual on" (immediate
    forced start) - that's the physical panel's override, not exposed here.
    """

    _attr_has_entity_name = True
    _attr_name = "Secomat auto dry"
    _attr_icon = "mdi:tumble-dryer"

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_auto_dry_switch"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("operating_mode") == POWER_MODE_READY

    async def async_turn_on(self, **kwargs) -> None:
        await self._send(CMD_WASH_AUTO)

    async def async_turn_off(self, **kwargs) -> None:
        await self._send(CMD_OFF)

    async def _send(self, command: str) -> None:
        try:
            await self.coordinator.client.async_send_command(command)
        except SecomatApiError as err:
            _LOGGER.error("Failed to send secomat command %s: %s", command, err)
            return
        await self.coordinator.async_request_refresh()


class SecomatRoomDryingSwitch(CoordinatorEntity[SecomatCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Secomat room drying"
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_room_drying_switch"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("room_drying_enabled"))

    async def async_turn_on(self, **kwargs) -> None:
        await self._send(CMD_ROOM_ON)

    async def async_turn_off(self, **kwargs) -> None:
        await self._send(CMD_ROOM_OFF)

    async def _send(self, command: str) -> None:
        try:
            await self.coordinator.client.async_send_command(command)
        except SecomatApiError as err:
            _LOGGER.error("Failed to send secomat command %s: %s", command, err)
            return
        await self.coordinator.async_request_refresh()

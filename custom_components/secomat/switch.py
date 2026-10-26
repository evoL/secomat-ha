"""Switch entities for drying modes and Secomat settings."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ARG_HMI_BACKLIGHT,
    ARG_WASH_LOCK_MOISTURE_TARGET,
    CMD_CHANGE,
    CMD_OFF,
    CMD_ROOM_OFF,
    CMD_ROOM_ON,
    CMD_WASH_AUTO,
    POWER_MODE_READY,
)
from .coordinator import SecomatConfigEntry, SecomatCoordinator
from .entity import SecomatEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SecomatConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            SecomatAutoDrySwitch(coordinator),
            SecomatRoomDryingSwitch(coordinator),
            SecomatTargetHumidityLockSwitch(coordinator),
            SecomatControlLightSwitch(coordinator),
        ]
    )


class SecomatAutoDrySwitch(SecomatEntity, SwitchEntity):
    """One-tap control for the secomat's 'Auto' drying mode (READY).

    On = Auto (the app's smart start-stop mode: waits for laundry, dries it
    automatically). Off = Off (STAND_BY). Doesn't touch "Manual on" (immediate
    forced start) - that's the physical panel's override, not exposed here.
    """

    _attr_name = "Auto dry"
    _attr_icon = "mdi:tumble-dryer"

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_auto_dry_switch"

    @property
    def is_on(self) -> bool:
        return self.coordinator.payload.get("operating_mode") == POWER_MODE_READY

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send_command(CMD_WASH_AUTO)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_send_command(CMD_OFF)


class SecomatRoomDryingSwitch(SecomatEntity, SwitchEntity):
    _attr_name = "Room drying"
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_room_drying_switch"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.payload.get("room_drying_enabled"))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send_command(CMD_ROOM_ON)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_send_command(CMD_ROOM_OFF)


class SecomatTargetHumidityLockSwitch(SecomatEntity, SwitchEntity):
    """Keep the chosen Target Humidity Level across drying cycles."""

    _attr_name = "Target humidity level lock"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_target_humidity_level_lock"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.payload.get("target_humidity_level_locked"))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send_command(CMD_CHANGE, {ARG_WASH_LOCK_MOISTURE_TARGET: 1})

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_send_command(CMD_CHANGE, {ARG_WASH_LOCK_MOISTURE_TARGET: 0})


class SecomatControlLightSwitch(SecomatEntity, SwitchEntity):
    """Control the status light on the Secomat's physical panel."""

    _attr_name = "Control light"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:lightbulb"

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_control_light"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.payload.get("hmi_backlight"))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send_command(CMD_CHANGE, {ARG_HMI_BACKLIGHT: 1})

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_send_command(CMD_CHANGE, {ARG_HMI_BACKLIGHT: 0})

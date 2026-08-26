"""Binary sensor entities for the Krüger Secomat integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SecomatCoordinator
from .const import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities: AddEntitiesCallback, discovery_info=None
) -> None:
    if discovery_info is None:
        return
    entities: list[BinarySensorEntity] = []
    for coordinator in hass.data.get(DOMAIN, {}).values():
        entities.extend(
            [
                SecomatLaundryDetectedSensor(coordinator),
                SecomatRoomDryingSensor(coordinator),
            ]
        )
    async_add_entities(entities)


class SecomatBinarySensorBase(CoordinatorEntity[SecomatCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_{self._key}"

    @property
    def _key(self) -> str:
        raise NotImplementedError


class SecomatLaundryDetectedSensor(SecomatBinarySensorBase):
    """The optical 'eye' sensor that detects hung laundry."""

    _attr_name = "Secomat laundry detected"
    _attr_icon = "mdi:tshirt-crew"
    _key = "eye_seeing_object"

    @property
    def is_on(self):
        value = self.coordinator.data.get("eye_seeing_object")
        return bool(value) if value is not None else None


class SecomatRoomDryingSensor(SecomatBinarySensorBase):
    """Whether 24h room-drying mode is currently enabled (mirrors the switch)."""

    _attr_name = "Secomat room drying enabled"
    _attr_icon = "mdi:fan"
    _key = "room_drying_enabled"

    @property
    def is_on(self):
        return bool(self.coordinator.data.get("room_drying_enabled"))

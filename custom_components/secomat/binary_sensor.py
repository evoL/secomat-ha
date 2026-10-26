"""Binary sensor entities for the Krüger Secomat integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SecomatConfigEntry, SecomatCoordinator
from .entity import SecomatEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SecomatConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [SecomatLaundryDetectedSensor(coordinator), SecomatRoomDryingSensor(coordinator)]
    )


class SecomatBinarySensorBase(SecomatEntity, BinarySensorEntity):
    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_{self._key}"

    @property
    def _key(self) -> str:
        raise NotImplementedError


class SecomatLaundryDetectedSensor(SecomatBinarySensorBase):
    """The optical 'eye' sensor that detects hung laundry."""

    _attr_name = "Laundry detected"
    _attr_icon = "mdi:tshirt-crew"
    _key = "eye_seeing_object"

    @property
    def is_on(self):
        value = self.coordinator.data.get("eye_seeing_object")
        return bool(value) if value is not None else None


class SecomatRoomDryingSensor(SecomatBinarySensorBase):
    """Whether 24h room-drying mode is currently enabled (mirrors the switch)."""

    _attr_name = "Room drying enabled"
    _attr_icon = "mdi:fan"
    _key = "room_drying_enabled"

    @property
    def is_on(self):
        return bool(self.coordinator.data.get("room_drying_enabled"))

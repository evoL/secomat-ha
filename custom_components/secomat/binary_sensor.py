"""Binary sensor entities for the Krüger Secomat integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SecomatConfigEntry, SecomatCoordinator
from .entity import SecomatEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SecomatConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            SecomatLaundryDetectedSensor(coordinator),
            SecomatConnectivitySensor(coordinator),
            SecomatDryingSensor(coordinator),
            SecomatProblemSensor(coordinator),
        ]
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
        value = self.coordinator.data.get("payload", {}).get("eye_seeing_object")
        return bool(value) if value is not None else None


class SecomatDryingSensor(SecomatBinarySensorBase):
    """Whether the Secomat is physically running, rather than merely armed."""

    _attr_name = "Drying"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _key = "drying"

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get("payload", {}).get("secomat_state")
        return value > 0 if value is not None else None


class SecomatProblemSensor(SecomatBinarySensorBase):
    """Active warnings and errors reported by the Secomat."""

    _attr_name = "Problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _key = "problem"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("payload", {}).get("error_list"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"errors": self.coordinator.data.get("payload", {}).get("error_list", [])}


class SecomatConnectivitySensor(SecomatBinarySensorBase):
    """The Secomat's live connection to the cloud, independent of cached readings."""

    _attr_name = "Connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _key = "connectivity"

    @property
    def available(self) -> bool:
        """Bypass only appliance connectivity; a failed cloud poll is unavailable."""
        return super(SecomatEntity, self).available

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_secomat_connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "source": self.coordinator.data.get("src"),
            "age": self.coordinator.data.get("age"),
        }

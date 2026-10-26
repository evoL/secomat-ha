"""Sensor entities for the Krüger Secomat integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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
            SecomatTemperatureSensor(coordinator),
            SecomatHumiditySensor(coordinator),
            SecomatDryingStateSensor(coordinator),
            SecomatDryingStateRawSensor(coordinator),
        ]
    )


class SecomatSensorBase(SecomatEntity, SensorEntity):
    def __init__(self, coordinator: SecomatCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"secomat_{coordinator.secomat_id}_{self._key}"

    @property
    def _key(self) -> str:
        raise NotImplementedError


class SecomatTemperatureSensor(SecomatSensorBase):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Temperature"
    _key = "temperature"

    @property
    def native_value(self):
        return self.coordinator.data.get("payload", {}).get("ambient_temperature")


class SecomatHumiditySensor(SecomatSensorBase):
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Humidity"
    _key = "humidity"

    @property
    def native_value(self):
        return self.coordinator.data.get("payload", {}).get("humidity")


class SecomatDryingStateSensor(SecomatSensorBase):
    """The physical fan and compressor state, including previously unseen values."""

    _attr_name = "Drying state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["Idle", "Fan only", "Drying", "Unknown"]
    _key = "drying_state"

    @property
    def native_value(self) -> str | None:
        value = self.coordinator.data.get("payload", {}).get("secomat_state")
        if value is None:
            return None
        return {0: "Idle", 2: "Fan only", 6: "Drying"}.get(value, "Unknown")


class SecomatDryingStateRawSensor(SecomatSensorBase):
    """Discrete raw states for history, without numeric measurement statistics."""

    _attr_name = "Drying state raw"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = None
    _key = "drying_state_raw"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("payload", {}).get("secomat_state")

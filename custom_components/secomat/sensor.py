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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SecomatCoordinator
from .const import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities: AddEntitiesCallback, discovery_info=None
) -> None:
    if discovery_info is None:
        return
    entities: list[SensorEntity] = []
    for coordinator in hass.data.get(DOMAIN, {}).values():
        entities.extend(
            [
                SecomatTemperatureSensor(coordinator),
                SecomatHumiditySensor(coordinator),
                SecomatTargetHumiditySensor(coordinator),
                SecomatFirmwareVersionSensor(coordinator),
            ]
        )
    async_add_entities(entities)


class SecomatSensorBase(CoordinatorEntity[SecomatCoordinator], SensorEntity):
    _attr_has_entity_name = True

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
    _attr_name = "Secomat temperature"
    _key = "temperature"

    @property
    def native_value(self):
        return self.coordinator.data.get("ambient_temperature")


class SecomatHumiditySensor(SecomatSensorBase):
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Secomat humidity"
    _key = "humidity"

    @property
    def native_value(self):
        return self.coordinator.data.get("humidity")


class SecomatTargetHumiditySensor(SecomatSensorBase):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Secomat target humidity level"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _key = "target_humidity_level"

    @property
    def native_value(self):
        return self.coordinator.data.get("target_humidity_level")


class SecomatFirmwareVersionSensor(SecomatSensorBase):
    _attr_name = "Secomat firmware version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _key = "fw_version"

    @property
    def native_value(self):
        return self.coordinator.data.get("fw_version")

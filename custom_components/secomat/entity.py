"""Common Device Registry link and naming behavior for Secomat entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SecomatCoordinator


class SecomatEntity(CoordinatorEntity[SecomatCoordinator]):
    """An entity belonging to a configured Secomat."""

    _attr_has_entity_name = True

    @property
    def available(self) -> bool:
        """Do not expose cached readings or controls as live appliance state."""
        return super().available and self.coordinator.is_secomat_connected

    @property
    def device_info(self) -> DeviceInfo:
        return self.coordinator.device_info

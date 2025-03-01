"""Sensor platform for Bokat.se integration."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BokatDataUpdateCoordinator
from .const import (
    DOMAIN,
    ATTR_ACTIVITY_NAME,
    ATTR_ACTIVITY_STATUS,
    ATTR_ACTIVITY_URL,
    ATTR_ACTIVITIES,
    DEFAULT_NAME,
    ICON,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Bokat.se sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Wait for first refresh so we have activity data
    await coordinator.async_config_entry_first_refresh()
    
    async_add_entities([BokatSensor(coordinator, entry)])


class BokatSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Bokat.se sensor."""

    def __init__(self, coordinator: BokatDataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}"
        
        # Use activity name for the entity name if available
        activity_name = "Unknown"
        if coordinator.data and coordinator.data.get("selected_activity"):
            activity_name = coordinator.data["selected_activity"].get("name", "Unknown")
        
        # Convert activity name to a valid entity ID format
        entity_name = re.sub(r'[^\w\s]', '', activity_name).lower().replace(' ', '_')
        
        self._attr_name = f"{DEFAULT_NAME} {entity_name}"
        self._attr_icon = ICON
        
        # Store the entity_id format for service calls
        coordinator.entity_id = f"sensor.bokat_se_{entity_name}"
        
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.data and self.coordinator.data.get("selected_activity"):
            return self.coordinator.data["selected_activity"].get("name", "Unknown")
        return "No activity"
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attrs = {}
        
        if self.coordinator.data and self.coordinator.data.get("selected_activity"):
            activity = self.coordinator.data["selected_activity"]
            attrs[ATTR_ACTIVITY_NAME] = activity.get("name", "Unknown")
            attrs[ATTR_ACTIVITY_STATUS] = activity.get("status", "Unknown")
            attrs[ATTR_ACTIVITY_URL] = activity.get("url", "Unknown")
        
        # Add all activities as an attribute
        if self.coordinator.data and self.coordinator.data.get("activities"):
            attrs[ATTR_ACTIVITIES] = [
                {
                    "name": activity.get("name", "Unknown"),
                    "status": activity.get("status", "Unknown"),
                    "url": activity.get("url", "Unknown"),
                }
                for activity in self.coordinator.data["activities"]
            ]
        
        return attrs 
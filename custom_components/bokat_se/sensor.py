"""Sensor platform for Bokat.se integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Import from the new location
from ..bokat_se_lib import BokatAPI

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bokat.se sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    # Wait for coordinator to get data
    await coordinator.async_config_entry_first_refresh()
    
    # Create a sensor for each activity
    sensors = []
    if coordinator.data:
        for activity in coordinator.data:
            sensors.append(BokatActivitySensor(coordinator, api, entry, activity))
    
    async_add_entities(sensors, True)


class BokatActivitySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Bokat.se activity sensor."""

    def __init__(self, coordinator, api, entry, activity):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._entry = entry
        self._activity = activity
        self._event_id = activity.get("eventId", "")
        
        # Set name and unique_id based on activity name and event_id
        activity_name = activity.get("name", "Unknown")
        group_name = activity.get("group", "Unknown Group")
        self._attr_name = f"Bokat {activity_name}"
        self._attr_unique_id = f"bokat_{self._event_id}"
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
            
        # Check if this activity is still in the coordinator data
        if self.coordinator.data:
            for activity in self.coordinator.data:
                if activity.get("eventId") == self._event_id:
                    self._activity = activity
                    return True
        return False

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        # Return totalAttending as the state
        return str(self._activity.get("total_attending", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        # Return all activity info as attributes, including participants
        attributes = dict(self._activity)
        
        # Keep the full participants list for the card
        # No need to remove participants or add participant_count
            
        return attributes 
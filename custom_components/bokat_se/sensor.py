"""Sensor platform for Bokat.se integration."""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Add the lib directory to the path
lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "lib")
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

from bokat_se import BokatAPI

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

    async_add_entities([BokatSensor(coordinator, api, entry)], True)


class BokatSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Bokat.se sensor."""

    def __init__(self, coordinator, api, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._api = api
        self._entry = entry
        self._attr_name = f"Bokat {entry.data['username']}"
        self._attr_unique_id = f"bokat_{entry.data['username']}"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return "No data"
        
        activities = self.coordinator.data
        return f"{len(activities)} activities"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
        
        activities = self.coordinator.data
        
        # Format activities for display
        formatted_activities = []
        for activity in activities:
            formatted_activities.append({
                "name": activity.get("name", "Unknown"),
                "group": activity.get("group", "Unknown Group"),
                "eventId": activity.get("eventId", ""),
                "userId": activity.get("userId", ""),
            })
        
        return {
            "activities": formatted_activities,
        } 
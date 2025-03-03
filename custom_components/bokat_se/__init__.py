"""The Bokat.se integration."""
from __future__ import annotations

import logging
import os
import sys
from datetime import timedelta
from typing import Any
from pathlib import Path

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.http import HomeAssistantView
from aiohttp import web

# Try to import from the HACS location first, then fall back to development location
try:
    from ._lib import BokatAPI
except ImportError:
    from ..bokat_se_lib import BokatAPI

from .const import DOMAIN, SCAN_INTERVAL, VERSION
from .frontend import async_register_frontend

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class BokatSeCardView(HomeAssistantView):
    """View to serve Bokat.se card from custom_components directory."""

    requires_auth = False
    url = r"/bokat_se/{path:.+}"
    name = "bokat_se_files"

    def __init__(self, component_path):
        """Initialize the view with the component path."""
        self.component_path = component_path

    async def get(self, request, path):
        """Serve the requested file."""
        file_path = Path(self.component_path) / "www" / path.split("?")[0]
        
        if not file_path.exists():
            return web.Response(status=404)
        
        with open(file_path, "r") as file:
            content = file.read()
        
        return web.Response(
            body=content,
            content_type="application/javascript",
            charset="utf-8"
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bokat.se component."""
    # Register the static path for serving the card
    component_path = Path(__file__).parent
    
    # Register the view for serving files
    hass.http.register_view(BokatSeCardView(component_path))
    
    # Register frontend resources
    await async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bokat.se from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    session = async_get_clientsession(hass)
    api = BokatAPI(session=session)

    # Register frontend resources
    await async_register_frontend(hass)

    async def async_update_data():
        """Fetch data from API."""
        try:
            # First, get the list of activities
            activities = await api.list_activities(username, password)
            
            # Then, get detailed info for each activity
            detailed_activities = []
            for activity in activities:
                event_id = activity.get("eventId")
                if event_id:
                    # Get detailed info for this activity
                    activity_info = await api.get_activity_info(event_id)
                    # Add basic activity info to the detailed info
                    activity_info.update({
                        "eventId": event_id,
                        "group": activity.get("group", "Unknown Group"),
                        "userId": activity.get("userId", ""),
                    })
                    detailed_activities.append(activity_info)
            
            return detailed_activities
        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err)
            raise UpdateFailed(f"Error fetching data: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok 
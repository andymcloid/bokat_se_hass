"""The Bokat.se integration."""
from __future__ import annotations

import logging
import os
from datetime import timedelta
from pathlib import Path

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
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

from .const import (
    DOMAIN, SCAN_INTERVAL, VERSION,
    SERVICE_REFRESH, SERVICE_RESPOND,
    ATTR_ENTITY_ID, ATTR_ATTENDANCE, ATTR_COMMENT, ATTR_GUESTS,
    CONF_ACTIVITY_URL
)

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

    # Register services
    async def handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service call."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        
        if entity_id:
            # First check if the entity exists
            state = hass.states.get(entity_id)
            if not state:
                _LOGGER.error("Entity %s not found", entity_id)
                return
                
            # Get the eventId from the entity's attributes
            event_id = state.attributes.get("eventId")
            if not event_id:
                _LOGGER.error("No eventId found in entity %s", entity_id)
                return
                
            # Find the coordinator for this entity
            entity_found = False
            
            for entry_data in hass.data[DOMAIN].values():
                coordinator = entry_data["coordinator"]
                if not coordinator.data:
                    continue
                    
                # Try to find a matching activity by eventId
                for activity in coordinator.data:
                    if activity.get("eventId") == event_id:
                        entity_found = True
                        await coordinator.async_refresh()
                        break
                        
                if entity_found:
                    break
            
            if not entity_found:
                _LOGGER.error("No coordinator found for entity %s (eventId: %s)", entity_id, event_id)
        else:
            # Refresh all coordinators
            for entry_data in hass.data[DOMAIN].values():
                coordinator = entry_data["coordinator"]
                await coordinator.async_refresh()

    async def handle_respond(call: ServiceCall) -> None:
        """Handle respond service call."""
        entity_id = call.data[ATTR_ENTITY_ID]
        attendance = call.data[ATTR_ATTENDANCE]
        # Ensure proper UTF-8 encoding for the comment
        comment = call.data.get(ATTR_COMMENT, "").encode('utf-8').decode('utf-8')
        guests = call.data.get(ATTR_GUESTS, 0)

        # First check if the entity exists
        state = hass.states.get(entity_id)
        if not state:
            _LOGGER.error("Entity %s not found", entity_id)
            return

        # Get the eventId from the entity's attributes
        event_id = state.attributes.get("eventId")
        user_id = state.attributes.get("userId")
        if not event_id or not user_id:
            _LOGGER.error("Missing eventId or userId for %s", entity_id)
            return

        # Find the coordinator and API instance for this entity
        api_found = False
        for entry_data in hass.data[DOMAIN].values():
            coordinator = entry_data["coordinator"]
            if not coordinator.data:
                continue

            # Try to find a matching activity by eventId
            for activity in coordinator.data:
                if activity.get("eventId") == event_id:
                    api = entry_data["api"]
                    api_found = True
                    break
            if api_found:
                break

        if not api_found:
            _LOGGER.error("No API instance found for entity %s (eventId: %s)", entity_id, event_id)
            return

        # Send the response
        success = await api.reply_to_activity(
            event_id=event_id,
            user_id=user_id,
            reply_type=attendance,
            comment=comment,
            guests=guests
        )

        if success:
            # Trigger a refresh
            await coordinator.async_refresh()
        else:
            _LOGGER.error("Failed to respond to activity")

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh)
    hass.services.async_register(DOMAIN, SERVICE_RESPOND, handle_respond)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bokat.se from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    session = async_get_clientsession(hass)
    api = BokatAPI(session=session)

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
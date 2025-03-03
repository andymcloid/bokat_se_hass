"""Frontend for Bokat.se integration."""
from __future__ import annotations

import os
from pathlib import Path

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_entry_flow as config_entry_flow

from .const import DOMAIN, VERSION

LOVELACE_CARD_ID = "bokat-se-card"
# Use a URL format similar to HACS with version for cache busting
LOVELACE_CARD_URL = f"/{DOMAIN}/{LOVELACE_CARD_ID}.js?hacstag={VERSION.replace('.', '')}"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the frontend resources."""
    # Register the card as a Lovelace resource
    # Use a URL format similar to HACS with version for cache busting
    resource_url = LOVELACE_CARD_URL
    
    # Check if Lovelace resources are available
    if "lovelace" in hass.data:
        # Use the proper accessor method instead of direct dictionary access
        resources = hass.data["lovelace"].resources
        
        # Check if the resource is already registered (ignoring version tag)
        resource_already_registered = False
        base_url = resource_url.split("?")[0]
        
        # Get all resources and check if our URL is already in the list
        for resource in resources.async_items():
            existing_url = resource["url"].split("?")[0] if "?" in resource["url"] else resource["url"]
            if existing_url == base_url:
                # If found but with old version, update it
                if resource["url"] != resource_url:
                    await resources.async_update_item(resource["id"], {"url": resource_url})
                resource_already_registered = True
                break
        
        # Register the resource if not already registered
        if not resource_already_registered:
            # Use the correct schema for creating resources
            await resources.async_create_item({"url": resource_url, "res_type": "module"}) 
"""Frontend for Bokat.se integration."""
from __future__ import annotations

import os
from pathlib import Path

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant

from .const import DOMAIN

LOVELACE_CARD_ID = "bokat-se-card"
LOVELACE_CARD_PATH = f"/{DOMAIN}/{LOVELACE_CARD_ID}.js"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the frontend resources."""
    # Copy the card file to the correct location
    www_dir = hass.config.path("www")
    if not os.path.exists(www_dir):
        os.makedirs(www_dir)
    
    # Path to the card in our component
    card_source_path = Path(__file__).parent / "www" / f"{LOVELACE_CARD_ID}.js"
    
    # Path where the card should be copied
    card_target_path = Path(www_dir) / f"{LOVELACE_CARD_ID}.js"
    
    # Copy the card file
    if card_source_path.exists():
        with open(card_source_path, "r") as source_file:
            card_content = source_file.read()
        
        with open(card_target_path, "w") as target_file:
            target_file.write(card_content)
    
    # Register the card as a Lovelace resource
    resource_url = f"/local/{LOVELACE_CARD_ID}.js"
    
    # Check if Lovelace resources are available
    if "lovelace" in hass.data:
        # Use the proper accessor method instead of direct dictionary access
        resources = hass.data["lovelace"].resources
        
        # Check if the resource is already registered
        resource_already_registered = False
        
        # Get all resources and check if our URL is already in the list
        for resource in resources.async_items():
            if resource["url"] == resource_url:
                resource_already_registered = True
                break
        
        # Register the resource if not already registered
        if not resource_already_registered:
            # Use the correct schema for creating resources
            await resources.async_create_item({"url": resource_url, "res_type": "module"}) 
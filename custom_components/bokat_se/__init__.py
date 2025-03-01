"""The Bokat.se integration."""
import asyncio
import logging
from datetime import timedelta

import aiohttp
import async_timeout
from bs4 import BeautifulSoup
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_ACTIVITY_URL

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)

SERVICE_REFRESH = "refresh"
SERVICE_SELECT_ACTIVITY = "select_activity"

SERVICE_SELECT_ACTIVITY_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("activity_url"): cv.string,
})

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Bokat.se component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Bokat.se from a config entry."""
    session = async_get_clientsession(hass)
    
    coordinator = BokatDataUpdateCoordinator(
        hass,
        _LOGGER,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        activity_url=entry.data.get(CONF_ACTIVITY_URL),
        session=session,
    )
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    
    # Register services
    async def handle_refresh(call: ServiceCall):
        """Handle the refresh service call."""
        entity_id = call.data.get("entity_id")
        
        # Find the coordinator for this entity
        for entry_id, coord in hass.data[DOMAIN].items():
            if f"sensor.bokat_se_{coord.username.split('@')[0]}" == entity_id:
                await coord.async_refresh()
                break
    
    async def handle_select_activity(call: ServiceCall):
        """Handle the select_activity service call."""
        entity_id = call.data.get("entity_id")
        activity_url = call.data.get("activity_url")
        
        # Find the coordinator for this entity
        for entry_id, coord in hass.data[DOMAIN].items():
            if f"sensor.bokat_se_{coord.username.split('@')[0]}" == entity_id:
                coord.activity_url = activity_url
                await coord.async_refresh()
                
                # Update the config entry
                new_data = dict(entry.data)
                new_data[CONF_ACTIVITY_URL] = activity_url
                hass.config_entries.async_update_entry(entry, data=new_data)
                break
    
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, handle_refresh
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_ACTIVITY, handle_select_activity, schema=SERVICE_SELECT_ACTIVITY_SCHEMA
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

class BokatDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Bokat.se data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        username: str,
        password: str,
        activity_url: str,
        session: aiohttp.ClientSession,
    ):
        """Initialize the coordinator."""
        self.username = username
        self.password = password
        self.activity_url = activity_url
        self.session = session
        self.activities = []
        self.selected_activity = None
        
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from Bokat.se."""
        try:
            async with async_timeout.timeout(30):
                return await self._fetch_bokat_data()
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout communicating with Bokat.se: {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with Bokat.se: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error occurred: {err}") from err

    async def _fetch_bokat_data(self):
        """Fetch data from Bokat.se."""
        # Login to Bokat.se
        login_url = "https://www.bokat.se/userPage.jsp"
        login_data = {
            "e": self.username,
            "l": self.password
        }
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.bokat.se",
            "Referer": "https://www.bokat.se/userPage.jsp",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Google Chrome\";v=\"133\", \"Chromium\";v=\"133\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\""
        }
        
        async with self.session.post(login_url, data=login_data, headers=headers) as response:
            if response.status != 200:
                raise UpdateFailed(f"Failed to login to Bokat.se: {response.status}")
            
            html = await response.text()
            
            # Parse the HTML to extract activities
            soup = BeautifulSoup(html, "html.parser")
            
            # Find all activities
            activities = []
            activity_rows = soup.find_all("tr", {"valign": "top", "align": "left", "class": "Text"})
            
            if not activity_rows:
                _LOGGER.warning("No activities found on Bokat.se")
                return {"activities": [], "selected_activity": None}
            
            # Process each activity
            current_activity = {}
            for row in soup.find_all("tr"):
                # Check if this is an activity header
                if row.find("b") and row.find("b").text == "Aktivitet:":
                    if current_activity and "name" in current_activity:
                        activities.append(current_activity)
                        current_activity = {}
                    
                    # Extract activity name
                    activity_name_cell = row.find_all("td")[-1]
                    if activity_name_cell:
                        current_activity["name"] = activity_name_cell.text.strip()
                
                # Check if this is a status row
                elif row.find("b") and row.find("b").text == "Status:":
                    status_cell = row.find_all("td")[-1]
                    if status_cell:
                        current_activity["status"] = status_cell.text.strip()
                
                # Check if this is a link row
                elif row.find("a", {"class": "ButtonLinkDynamic"}):
                    link = row.find("a", {"class": "ButtonLinkDynamic"})
                    if link and "href" in link.attrs:
                        current_activity["url"] = f"https://www.bokat.se/{link['href']}"
            
            # Add the last activity if it exists
            if current_activity and "name" in current_activity:
                activities.append(current_activity)
            
            self.activities = activities
            
            # If we have an activity URL, find the matching activity
            if self.activity_url:
                for activity in activities:
                    if activity["url"] == self.activity_url:
                        self.selected_activity = activity
                        break
            # Otherwise, use the first activity
            elif activities:
                self.selected_activity = activities[0]
            else:
                self.selected_activity = None
            
            return {
                "activities": activities,
                "selected_activity": self.selected_activity
            } 
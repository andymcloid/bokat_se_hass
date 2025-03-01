"""The Bokat.se integration."""
import asyncio
import logging
import os
import shutil
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

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACTIVITY_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    SERVICE_REFRESH,
    SERVICE_SELECT_ACTIVITY,
    SERVICE_RESPOND,
    ATTR_ENTITY_ID,
    ATTR_ACTIVITY_URL,
    ATTR_ATTENDANCE,
    ATTR_COMMENT,
    ATTR_GUESTS,
    ATTENDANCE_YES,
    ATTENDANCE_NO,
    ATTENDANCE_COMMENT_ONLY,
)

_LOGGER = logging.getLogger(__name__)

# This is no longer used as we get the scan interval from the config entry
# SCAN_INTERVAL = timedelta(minutes=30)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Bokat.se component."""
    hass.data.setdefault(DOMAIN, {})
    
    # Copy the frontend card to the www directory
    await hass.async_add_executor_job(copy_frontend_card, hass)
    
    return True

def copy_frontend_card(hass: HomeAssistant) -> None:
    """Copy the frontend card to the www directory and register it as a resource."""
    # Get the path to the www directory
    www_dir = os.path.join(hass.config.path(), "www")
    
    # Create the www directory if it doesn't exist
    if not os.path.exists(www_dir):
        os.makedirs(www_dir)
        _LOGGER.info("Created www directory at %s", www_dir)
    
    # Get the path to the frontend card
    component_dir = os.path.dirname(os.path.dirname(__file__))
    card_src = os.path.join(component_dir, "www", "bokat-se-card.js")
    
    # Check if the card exists in the component directory
    if os.path.exists(card_src):
        # Copy the card to the www directory
        card_dest = os.path.join(www_dir, "bokat-se-card.js")
        shutil.copy2(card_src, card_dest)
        _LOGGER.info("Copied Bokat.se card to www directory: %s", card_dest)
        
        # Try to register the card as a resource in Home Assistant
        resource_url = "/local/bokat-se-card.js"
        
        # First method: Try using the resources module directly
        try:
            import homeassistant.components.lovelace.resources as resources
            resource_type = "module"
            
            # Check if the resource already exists
            if hasattr(resources, "async_get_resource_list") and hasattr(resources, "async_create_resource"):
                async def register_resource():
                    try:
                        # Wait a bit to ensure Lovelace is fully initialized
                        await asyncio.sleep(10)
                        
                        resource_list = await resources.async_get_resource_list(hass)
                        for resource in resource_list:
                            if resource["url"] == resource_url:
                                _LOGGER.info("Bokat.se card already registered as a resource")
                                return
                        
                        # Register the resource
                        try:
                            await resources.async_create_resource(hass, resource_url, resource_type)
                            _LOGGER.info("Successfully registered Bokat.se card as a resource")
                        except Exception as e:
                            _LOGGER.warning("Failed to register Bokat.se card as a resource: %s", e)
                            _LOGGER.warning("Please manually add the resource in the Lovelace UI:")
                            _LOGGER.warning("  1. Go to Configuration → Lovelace Dashboards → Resources")
                            _LOGGER.warning("  2. Add '/local/bokat-se-card.js' as a JavaScript Module")
                    except Exception as e:
                        _LOGGER.warning("Error during resource registration: %s", e)
                
                # Schedule the registration
                hass.async_create_task(register_resource())
            else:
                _LOGGER.warning("Could not register Bokat.se card as a resource: API not available")
                _LOGGER.warning("Please manually add the resource in the Lovelace UI:")
                _LOGGER.warning("  1. Go to Configuration → Lovelace Dashboards → Resources")
                _LOGGER.warning("  2. Add '/local/bokat-se-card.js' as a JavaScript Module")
        except ImportError:
            _LOGGER.warning("Could not register Bokat.se card as a resource: Lovelace resources module not available")
            _LOGGER.warning("Please manually add the resource in the Lovelace UI:")
            _LOGGER.warning("  1. Go to Configuration → Lovelace Dashboards → Resources")
            _LOGGER.warning("  2. Add '/local/bokat-se-card.js' as a JavaScript Module")
    else:
        _LOGGER.warning("Bokat.se card not found in component directory: %s", card_src)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bokat.se from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    activity_url = entry.data.get(CONF_ACTIVITY_URL)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    
    session = async_get_clientsession(hass)
    
    coordinator = BokatDataUpdateCoordinator(
        hass,
        _LOGGER,
        username=username,
        password=password,
        activity_url=activity_url,
        session=session,
        scan_interval=scan_interval,
    )
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    
    async def handle_refresh(call):
        """Handle the refresh service call."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        
        if not entity_id:
            # Refresh all entities
            for coordinator in hass.data[DOMAIN].values():
                await coordinator.async_refresh()
            return
        
        # Find the coordinator for this entity
        for coordinator in hass.data[DOMAIN].values():
            if coordinator.entity_id == entity_id:
                await coordinator.async_refresh()
                return
    
    async def handle_select_activity(call):
        """Handle the select activity service call."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        activity_url = call.data.get(ATTR_ACTIVITY_URL)
        
        if not entity_id or not activity_url:
            _LOGGER.error("Both entity_id and activity_url are required")
            return
        
        # Find the coordinator for this entity
        for coordinator in hass.data[DOMAIN].values():
            if coordinator.entity_id == entity_id:
                coordinator.activity_url = activity_url
                await coordinator.async_refresh()
                return
    
    async def handle_respond(call):
        """Handle the respond service call."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        attendance = call.data.get(ATTR_ATTENDANCE)
        comment = call.data.get(ATTR_COMMENT, "")
        guests = call.data.get(ATTR_GUESTS, 0)
        
        if not entity_id:
            _LOGGER.error("entity_id is required")
            return
        
        if attendance not in [ATTENDANCE_YES, ATTENDANCE_NO, ATTENDANCE_COMMENT_ONLY]:
            _LOGGER.error(f"Invalid attendance value: {attendance}")
            return
        
        # Find the coordinator for this entity
        for coordinator in hass.data[DOMAIN].values():
            if coordinator.entity_id == entity_id:
                await coordinator.async_respond_to_event(attendance, comment, guests)
                await coordinator.async_refresh()
                return
    
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, handle_refresh, schema=vol.Schema({
            vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
        })
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_ACTIVITY, handle_select_activity, schema=vol.Schema({
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Required(ATTR_ACTIVITY_URL): cv.string,
        })
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_RESPOND, handle_respond, schema=vol.Schema({
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Required(ATTR_ATTENDANCE): vol.In([ATTENDANCE_YES, ATTENDANCE_NO, ATTENDANCE_COMMENT_ONLY]),
            vol.Optional(ATTR_COMMENT): cv.string,
            vol.Optional(ATTR_GUESTS, default=0): vol.Coerce(int),
        })
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
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ):
        """Initialize the coordinator."""
        self.username = username
        self.password = password
        self.activity_url = activity_url
        self.session = session
        self.activities = []
        self.selected_activity = None
        self.entity_id = None  # Will be set by the sensor
        
        update_interval = timedelta(minutes=scan_interval)
        
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval,
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
                        # Fetch participant information for the selected activity
                        participant_data = await self._fetch_participant_data(self.activity_url)
                        if participant_data:
                            self.selected_activity.update(participant_data)
                        break
            # Otherwise, use the first activity
            elif activities:
                self.selected_activity = activities[0]
                # Fetch participant information for the first activity
                participant_data = await self._fetch_participant_data(activities[0]["url"])
                if participant_data:
                    self.selected_activity.update(participant_data)
            else:
                self.selected_activity = None
            
            return {
                "activities": activities,
                "selected_activity": self.selected_activity
            }
            
    async def _fetch_participant_data(self, activity_url):
        """Fetch participant data from the activity page."""
        if not activity_url:
            return None
            
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
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
        
        try:
            async with self.session.get(activity_url, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(f"Failed to fetch activity page: {response.status}")
                    return None
                
                html = await response.text()
                
                # Parse the HTML to extract participant information
                soup = BeautifulSoup(html, "html.parser")
                
                # Find the participant table
                participant_table = soup.find("table", {"class": "TableList"})
                if not participant_table:
                    _LOGGER.warning("No participant table found on activity page")
                    return None
                
                # Find all participant rows
                participant_rows = participant_table.find_all("tr", {"class": ["RowOdd", "RowEven"]})
                
                participants = []
                attending_count = 0
                not_attending_count = 0
                no_response_count = 0
                
                for row in participant_rows:
                    cells = row.find_all("td")
                    if len(cells) >= 4:
                        name = cells[0].text.strip()
                        status_cell = cells[1]
                        status_img = status_cell.find("img")
                        
                        status = "unknown"
                        if status_img and "src" in status_img.attrs:
                            src = status_img["src"]
                            if "yes.gif" in src:
                                status = "attending"
                                attending_count += 1
                            elif "no.gif" in src:
                                status = "not_attending"
                                not_attending_count += 1
                            else:
                                status = "no_response"
                                no_response_count += 1
                        
                        comment = cells[2].text.strip() if len(cells) > 2 else ""
                        timestamp = cells[3].text.strip() if len(cells) > 3 else ""
                        
                        participants.append({
                            "name": name,
                            "status": status,
                            "comment": comment,
                            "timestamp": timestamp
                        })
                
                # Find the answer URL if available
                answer_url = None
                answer_link = soup.find("a", string=lambda s: s and "Svara" in s)
                if answer_link and "href" in answer_link.attrs:
                    answer_url = f"https://www.bokat.se/{answer_link['href']}"
                
                return {
                    "participants": participants,
                    "total_participants": len(participants),
                    "attending_count": attending_count,
                    "not_attending_count": not_attending_count,
                    "no_response_count": no_response_count,
                    "answer_url": answer_url
                }
                
        except Exception as err:
            _LOGGER.error(f"Error fetching participant data: {err}")
            return None
            
    async def async_respond_to_event(self, attendance, comment, guests):
        """Respond to an event with attendance status, comment, and guests."""
        if not self.selected_activity or "answer_url" not in self.selected_activity:
            _LOGGER.error("No selected activity or answer URL available")
            return False
            
        answer_url = self.selected_activity["answer_url"]
        if not answer_url:
            _LOGGER.error("No answer URL available for the selected activity")
            return False
            
        try:
            # First, get the answer page to extract the form parameters
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "keep-alive",
                "Referer": self.activity_url,
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
            
            async with self.session.get(answer_url, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(f"Failed to fetch answer page: {response.status}")
                    return False
                
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                
                # Find the form and extract hidden fields
                form = soup.find("form")
                if not form:
                    _LOGGER.error("No form found on answer page")
                    return False
                
                # Prepare form data
                form_data = {}
                
                # Add hidden fields
                for hidden_field in form.find_all("input", {"type": "hidden"}):
                    if "name" in hidden_field.attrs and "value" in hidden_field.attrs:
                        form_data[hidden_field["name"]] = hidden_field["value"]
                
                # Set attendance status
                if attendance == ATTENDANCE_YES:
                    form_data["answer"] = "yes"
                elif attendance == ATTENDANCE_NO:
                    form_data["answer"] = "no"
                else:  # ATTENDANCE_COMMENT_ONLY
                    # Just update the comment without changing attendance
                    if "answer" in form_data:
                        pass  # Keep existing value
                    else:
                        form_data["answer"] = ""  # Default to empty if not found
                
                # Add comment if provided
                if comment:
                    form_data["comment"] = comment
                
                # Add guests if attending
                if attendance == ATTENDANCE_YES and guests > 0:
                    form_data["guests"] = str(guests)
                
                # Find the submit URL
                action_url = form.get("action", "")
                if not action_url:
                    _LOGGER.error("No form action URL found")
                    return False
                
                submit_url = f"https://www.bokat.se/{action_url}"
                
                # Submit the form
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                headers["Origin"] = "https://www.bokat.se"
                headers["Referer"] = answer_url
                
                async with self.session.post(submit_url, data=form_data, headers=headers) as submit_response:
                    if submit_response.status != 200:
                        _LOGGER.error(f"Failed to submit response: {submit_response.status}")
                        return False
                    
                    _LOGGER.info(f"Successfully responded to event with status: {attendance}")
                    return True
                    
        except Exception as err:
            _LOGGER.error(f"Error responding to event: {err}")
            return False 
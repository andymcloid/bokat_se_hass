"""Config flow for Bokat.se integration."""
import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp
import async_timeout
from bs4 import BeautifulSoup
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_ACTIVITY_URL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)

    login_url = "https://www.bokat.se/userPage.jsp"
    login_data = {
        "e": data[CONF_USERNAME],
        "l": data[CONF_PASSWORD]
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

    try:
        async with async_timeout.timeout(30):
            async with session.post(login_url, data=login_data, headers=headers) as response:
                if response.status != 200:
                    raise InvalidAuth("Invalid authentication")
                
                html = await response.text()
                
                # Check if login was successful by looking for activities
                soup = BeautifulSoup(html, "html.parser")
                
                # Find all activities
                activities = []
                activity_rows = soup.find_all("tr", {"valign": "top", "align": "left", "class": "Text"})
                
                if not activity_rows:
                    # Check if there's an error message
                    if "Felaktigt användarnamn eller lösenord" in html:
                        raise InvalidAuth("Invalid username or password")
                    else:
                        _LOGGER.warning("No activities found on Bokat.se")
                
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
                    
                    # Check if this is a link row
                    elif row.find("a", {"class": "ButtonLinkDynamic"}):
                        link = row.find("a", {"class": "ButtonLinkDynamic"})
                        if link and "href" in link.attrs:
                            current_activity["url"] = f"https://www.bokat.se/{link['href']}"
                
                # Add the last activity if it exists
                if current_activity and "name" in current_activity:
                    activities.append(current_activity)
                
                return {"activities": activities}
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Error connecting to Bokat.se: {err}") from err
    except asyncio.TimeoutError as err:
        raise CannotConnect(f"Timeout connecting to Bokat.se: {err}") from err
    except Exception as err:
        raise CannotConnect(f"Unexpected error: {err}") from err


class BokatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bokat.se."""

    VERSION = 1
    
    def __init__(self):
        """Initialize the config flow."""
        self.data = {}
        self.activities = []

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                self.data = user_input
                self.activities = info["activities"]
                
                # If we have activities, go to the activity selection step
                if self.activities:
                    return await self.async_step_activity()
                
                # Otherwise, create the entry with just the login info
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=self.data
                )
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_activity(self, user_input=None):
        """Handle the activity selection step."""
        if user_input is not None:
            self.data[CONF_ACTIVITY_URL] = user_input[CONF_ACTIVITY_URL]
            
            return self.async_create_entry(
                title=self.data[CONF_USERNAME],
                data=self.data
            )
        
        # Create a schema with a dropdown of activities
        activity_schema = vol.Schema(
            {
                vol.Required(CONF_ACTIVITY_URL): vol.In(
                    {activity["url"]: activity["name"] for activity in self.activities}
                )
            }
        )
        
        return self.async_show_form(
            step_id="activity",
            data_schema=activity_schema,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth.""" 
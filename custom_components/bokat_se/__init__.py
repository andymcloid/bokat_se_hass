"""The Bokat.se integration."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
from datetime import timedelta
from typing import Any, Dict, Optional

import aiohttp
import async_timeout
from bs4 import BeautifulSoup
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_ACTIVITY_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    SERVICE_REFRESH,
    SERVICE_SELECT_ACTIVITY,
    SERVICE_RESPOND,
    ATTR_ENTITY_ID,
    ATTR_ATTENDANCE,
    ATTR_COMMENT,
    ATTR_GUESTS,
    ATTENDANCE_YES,
    ATTENDANCE_NO,
    ATTENDANCE_COMMENT_ONLY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

# Service schema for respond service
RESPOND_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_ATTENDANCE): vol.In([ATTENDANCE_YES, ATTENDANCE_NO, ATTENDANCE_COMMENT_ONLY]),
        vol.Optional(ATTR_GUESTS, default=0): cv.positive_int,
        vol.Optional(ATTR_COMMENT, default=""): cv.string,
    }
)

# Service schema for select_activity service
SELECT_ACTIVITY_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_ACTIVITY_URL): cv.string,
    }
)

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
    component_dir = os.path.dirname(__file__)
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
    session = async_get_clientsession(hass)
    
    # Create API client
    client = BokatApiClient(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    
    # Create coordinator
    coordinator = BokatDataUpdateCoordinator(
        hass=hass,
        client=client,
        name="Bokat.se",
        update_interval=timedelta(minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        activity_url=entry.data.get(CONF_ACTIVITY_URL),
    )
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    async def handle_refresh(call: ServiceCall) -> None:
        """Handle the refresh service call."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        
        # Find the coordinator for this entity
        for entry_id, coord in hass.data[DOMAIN].items():
            if coord.entity_id == entity_id:
                await coord.async_refresh()
                break
    
    async def handle_select_activity(call: ServiceCall) -> None:
        """Handle the select activity service call."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        activity_url = call.data.get(CONF_ACTIVITY_URL)
        
        # Find the coordinator for this entity
        for entry_id, coord in hass.data[DOMAIN].items():
            if coord.entity_id == entity_id:
                coord.activity_url = activity_url
                await coord.async_refresh()
                break
    
    async def handle_respond(call: ServiceCall) -> None:
        """Handle the respond service call."""
        entity_id = call.data.get(ATTR_ENTITY_ID)
        attendance = call.data.get(ATTR_ATTENDANCE)
        guests = call.data.get(ATTR_GUESTS, 0)
        comment = call.data.get(ATTR_COMMENT, "")
        
        # Find the coordinator for this entity
        for entry_id, coord in hass.data[DOMAIN].items():
            if coord.entity_id == entity_id:
                await coord.client.submit_response(
                    activity_url=coord.activity_url,
                    attendance=attendance,
                    guests=guests,
                    comment=comment
                )
                await coord.async_refresh()
                break
    
    # Register services
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, handle_refresh, schema=vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_id})
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_ACTIVITY, handle_select_activity, schema=SELECT_ACTIVITY_SERVICE_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_RESPOND, handle_respond, schema=RESPOND_SERVICE_SCHEMA
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unload_ok

class BokatApiClient:
    """API client for Bokat.se."""
    
    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self._cookies = None
    
    async def login(self) -> bool:
        """Log in to Bokat.se."""
        # Try the standard login method first
        if await self._login_standard():
            return True
        
        # If standard login fails, try the alternative method
        _LOGGER.debug("Standard login failed, trying alternative method")
        if await self._login_alternative():
            return True
            
        # If alternative login fails, try the browser simulation method
        _LOGGER.debug("Alternative login failed, trying browser simulation method")
        if await self._login_browser_simulation():
            return True
            
        # If all else fails, try the direct HTTP method
        _LOGGER.debug("Browser simulation failed, trying direct HTTP method")
        if await self._login_direct_http():
            return True
            
        # Final fallback - try a completely different approach
        _LOGGER.debug("All login methods failed, trying final fallback method")
        return await self._login_final_fallback()
    
    async def _login_standard(self) -> bool:
        """Standard login method using form submission."""
        try:
            _LOGGER.debug("Attempting standard login to Bokat.se with username: %s", self._username)
            
            async with async_timeout.timeout(10):
                # First try with allow_redirects=True to follow any redirects
                response = await self._session.post(
                    "https://www.bokat.se/login.jsp",
                    data={
                        "username": self._username,
                        "password": self._password,
                        "login": "Logga in",
                    },
                    allow_redirects=True,
                )
                
                _LOGGER.debug("Login response status: %s", response.status)
                _LOGGER.debug("Login response URL: %s", response.url)
                
                # Store cookies regardless of status
                self._cookies = response.cookies
                cookie_count = len(self._cookies) if self._cookies else 0
                _LOGGER.debug("Received %d cookies from login response", cookie_count)
                
                # If we got a 200 response, check the content
                html = await response.text()
                
                # Log the first 100 characters of the response for debugging
                preview = html[:100].replace('\n', ' ').strip()
                _LOGGER.debug("Response preview: %s...", preview)
                
                # Check for login success indicators
                has_logout = "Logga ut" in html
                has_activities = "Mina aktiviteter" in html
                has_login_form = "login.jsp" in html or "Logga in" in html
                
                _LOGGER.debug("Login indicators - Logout link: %s, Activities link: %s, Login form: %s", 
                             has_logout, has_activities, has_login_form)
                
                # If we see logout or activities links, we're logged in
                if has_logout or has_activities:
                    _LOGGER.info("Successfully logged in to Bokat.se (found success indicators)")
                    return True
                
                # If we don't see the login form anymore, we might be logged in
                if not has_login_form:
                    _LOGGER.info("Login appears successful (login form not present)")
                    return True
                
                # If we have cookies, try a follow-up request
                if cookie_count > 0:
                    _LOGGER.debug("Verifying login with follow-up request")
                    try:
                        check_response = await self._session.get(
                            "https://www.bokat.se/myActivities.jsp",
                            cookies=self._cookies,
                        )
                        
                        _LOGGER.debug("Verification response status: %s", check_response.status)
                        
                        if check_response.status == 200:
                            check_html = await check_response.text()
                            check_has_login = "Logga in" in check_html or "login.jsp" in check_html
                            
                            if not check_has_login:
                                _LOGGER.info("Login verified with follow-up request")
                                return True
                            else:
                                _LOGGER.debug("Follow-up request shows login form, authentication failed")
                        else:
                            _LOGGER.debug("Follow-up request failed with status: %s", check_response.status)
                    except Exception as e:
                        _LOGGER.warning("Error during login verification: %s", e)
                
                # Try one more approach - direct access to the main page
                try:
                    _LOGGER.debug("Trying direct access to main page")
                    main_response = await self._session.get(
                        "https://www.bokat.se/",
                        cookies=self._cookies,
                    )
                    
                    if main_response.status == 200:
                        main_html = await main_response.text()
                        if "Logga ut" in main_html and "Mina aktiviteter" in main_html:
                            _LOGGER.info("Login verified with main page access")
                            return True
                except Exception as e:
                    _LOGGER.warning("Error during main page check: %s", e)
                
                _LOGGER.debug("Standard login method failed")
                return False
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error in standard login to Bokat.se: %s", err)
            return False
    
    async def _login_alternative(self) -> bool:
        """Alternative login method using a two-step process."""
        try:
            _LOGGER.debug("Attempting alternative login to Bokat.se")
            
            # Step 1: Get the login page to capture any cookies and CSRF tokens
            async with async_timeout.timeout(10):
                login_page_response = await self._session.get(
                    "https://www.bokat.se/login.jsp",
                )
                
                _LOGGER.debug("Login page response status: %s", login_page_response.status)
                
                # Store initial cookies
                initial_cookies = login_page_response.cookies
                _LOGGER.debug("Received %d cookies from login page", 
                             len(initial_cookies) if initial_cookies else 0)
                
                # Try to extract any CSRF token or hidden fields
                login_html = await login_page_response.text()
                form_data = {
                    "username": self._username,
                    "password": self._password,
                    "login": "Logga in",
                }
                
                try:
                    soup = BeautifulSoup(login_html, 'html.parser')
                    form = soup.find('form', action=lambda x: x and 'login.jsp' in x)
                    
                    if form:
                        # Extract all hidden fields
                        hidden_fields = form.find_all('input', type='hidden')
                        for field in hidden_fields:
                            name = field.get('name')
                            value = field.get('value')
                            if name and name not in form_data:
                                form_data[name] = value
                                _LOGGER.debug("Found hidden field: %s", name)
                except Exception as e:
                    _LOGGER.warning("Error extracting form fields: %s", e)
            
            # Step 2: Submit the login form with all cookies and fields
            async with async_timeout.timeout(10):
                # Use a new session for this request
                login_response = await self._session.post(
                    "https://www.bokat.se/login.jsp",
                    data=form_data,
                    cookies=initial_cookies,
                    allow_redirects=True,
                    headers={
                        "Referer": "https://www.bokat.se/login.jsp",
                        "Origin": "https://www.bokat.se",
                        "Content-Type": "application/x-www-form-urlencoded",
                    }
                )
                
                _LOGGER.debug("Alternative login response status: %s", login_response.status)
                _LOGGER.debug("Alternative login response URL: %s", login_response.url)
                
                # Merge cookies
                if initial_cookies:
                    self._cookies = initial_cookies
                
                # Update with new cookies
                if login_response.cookies:
                    for key, value in login_response.cookies.items():
                        self._cookies[key] = value
                
                # Check if login was successful
                response_html = await login_response.text()
                
                # Check for success indicators
                if "Logga ut" in response_html or "Mina aktiviteter" in response_html:
                    _LOGGER.info("Alternative login successful")
                    return True
                
                # If we're redirected to the main page or activities page, we're logged in
                if "login.jsp" not in str(login_response.url) and "Logga in" not in response_html:
                    _LOGGER.info("Alternative login appears successful based on URL")
                    return True
                
                # Final verification - try to access a protected page
                try:
                    verify_response = await self._session.get(
                        "https://www.bokat.se/myActivities.jsp",
                        cookies=self._cookies,
                    )
                    
                    if verify_response.status == 200:
                        verify_html = await verify_response.text()
                        if "Logga in" not in verify_html and "login.jsp" not in verify_html:
                            _LOGGER.info("Alternative login verified with activities page")
                            return True
                except Exception as e:
                    _LOGGER.warning("Error during alternative login verification: %s", e)
                
                _LOGGER.error("Alternative login method failed")
                return False
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error in alternative login to Bokat.se: %s", err)
            return False
    
    async def _login_browser_simulation(self) -> bool:
        """Login method that simulates a browser more closely."""
        try:
            _LOGGER.debug("Attempting browser simulation login to Bokat.se")
            
            # Create a new ClientSession with browser-like headers
            browser_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
            }
            
            # Step 1: Visit the main page first to get initial cookies
            async with async_timeout.timeout(10):
                main_response = await self._session.get(
                    "https://www.bokat.se/",
                    headers=browser_headers,
                )
                
                _LOGGER.debug("Main page response status: %s", main_response.status)
                
                # Store cookies
                main_cookies = main_response.cookies
            
            # Step 2: Visit the login page to get any session cookies or tokens
            async with async_timeout.timeout(10):
                login_page_response = await self._session.get(
                    "https://www.bokat.se/login.jsp",
                    headers=browser_headers,
                    cookies=main_cookies,
                )
                
                _LOGGER.debug("Login page response status: %s", login_page_response.status)
                
                # Merge cookies
                login_page_cookies = login_page_response.cookies
                for key, value in login_page_cookies.items():
                    main_cookies[key] = value
                
                # Extract any hidden form fields
                login_html = await login_page_response.text()
                form_data = {
                    "username": self._username,
                    "password": self._password,
                    "login": "Logga in",
                }
                
                try:
                    soup = BeautifulSoup(login_html, 'html.parser')
                    form = soup.find('form', action=lambda x: x and 'login.jsp' in x)
                    
                    if form:
                        # Get the form action URL
                        form_action = form.get('action', 'login.jsp')
                        login_url = f"https://www.bokat.se/{form_action}" if not form_action.startswith('http') else form_action
                        
                        # Extract all input fields (not just hidden)
                        input_fields = form.find_all('input')
                        for field in input_fields:
                            name = field.get('name')
                            value = field.get('value', '')
                            field_type = field.get('type', '')
                            
                            # Skip username and password fields as we'll set those explicitly
                            if name and name not in ['username', 'password'] and field_type != 'submit':
                                form_data[name] = value
                                _LOGGER.debug("Found form field: %s = %s", name, value)
                except Exception as e:
                    _LOGGER.warning("Error extracting form fields: %s", e)
                    login_url = "https://www.bokat.se/login.jsp"
            
            # Step 3: Submit the login form with all cookies and proper headers
            async with async_timeout.timeout(10):
                # Add referer and other browser-like headers
                submit_headers = browser_headers.copy()
                submit_headers.update({
                    "Referer": "https://www.bokat.se/login.jsp",
                    "Origin": "https://www.bokat.se",
                    "Content-Type": "application/x-www-form-urlencoded",
                })
                
                login_response = await self._session.post(
                    login_url,
                    data=form_data,
                    headers=submit_headers,
                    cookies=main_cookies,
                    allow_redirects=True,
                )
                
                _LOGGER.debug("Browser login response status: %s", login_response.status)
                _LOGGER.debug("Browser login response URL: %s", login_response.url)
                
                # Update cookies with any new ones
                for key, value in login_response.cookies.items():
                    main_cookies[key] = value
                
                # Store the final cookies
                self._cookies = main_cookies
                
                # Check if login was successful
                response_html = await login_response.text()
                
                # Check for success indicators
                if "Logga ut" in response_html:
                    _LOGGER.info("Browser simulation login successful (found logout link)")
                    return True
                
                if "Mina aktiviteter" in response_html:
                    _LOGGER.info("Browser simulation login successful (found activities link)")
                    return True
                
                # If we're redirected away from login page, we might be logged in
                if "login.jsp" not in str(login_response.url) and "Logga in" not in response_html:
                    _LOGGER.info("Browser simulation login appears successful based on URL")
                    
                    # Verify by accessing a protected page
                    try:
                        verify_response = await self._session.get(
                            "https://www.bokat.se/myActivities.jsp",
                            headers=browser_headers,
                            cookies=self._cookies,
                        )
                        
                        if verify_response.status == 200:
                            verify_html = await verify_response.text()
                            if "Logga in" not in verify_html:
                                _LOGGER.info("Browser simulation login verified with activities page")
                                return True
                    except Exception as e:
                        _LOGGER.warning("Error during browser login verification: %s", e)
                
                # If all else fails, dump the HTML for debugging
                _LOGGER.debug("Login failed. Response HTML preview: %s", response_html[:200].replace('\n', ' '))
                _LOGGER.error("Browser simulation login method failed")
                return False
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error in browser simulation login to Bokat.se: %s", err)
            return False
    
    async def _login_direct_http(self) -> bool:
        """Login method using direct HTTP requests with minimal dependencies."""
        try:
            _LOGGER.debug("Attempting direct HTTP login to Bokat.se")
            
            # Create a completely new session with minimal configuration
            async with aiohttp.ClientSession() as new_session:
                # Step 1: Get the login page to capture cookies
                async with new_session.get("https://www.bokat.se/login.jsp") as login_page_response:
                    _LOGGER.debug("Login page status: %s", login_page_response.status)
                    
                    # Get cookies from the login page
                    cookies = login_page_response.cookies
                    _LOGGER.debug("Login page cookies: %s", cookies)
                    
                    # Get the login page content
                    login_page_html = await login_page_response.text()
                
                # Step 2: Submit the login form
                form_data = {
                    "username": self._username,
                    "password": self._password,
                    "login": "Logga in"
                }
                
                # Add any hidden fields from the form
                try:
                    import re
                    hidden_fields = re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', login_page_html)
                    for name, value in hidden_fields:
                        form_data[name] = value
                        _LOGGER.debug("Found hidden field: %s = %s", name, value)
                except Exception as e:
                    _LOGGER.warning("Error extracting hidden fields: %s", e)
                
                # Submit the form
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": "https://www.bokat.se/login.jsp",
                    "Origin": "https://www.bokat.se"
                }
                
                async with new_session.post(
                    "https://www.bokat.se/login.jsp",
                    data=form_data,
                    cookies=cookies,
                    headers=headers,
                    allow_redirects=True
                ) as login_response:
                    _LOGGER.debug("Login response status: %s", login_response.status)
                    _LOGGER.debug("Login response URL: %s", login_response.url)
                    
                    # Get the response content
                    response_html = await login_response.text()
                    
                    # Check for success indicators
                    login_success = (
                        "Logga ut" in response_html or
                        "Mina aktiviteter" in response_html or
                        ("login.jsp" not in str(login_response.url) and "Logga in" not in response_html)
                    )
                    
                    if login_success:
                        # Copy all cookies to our main session
                        self._cookies = login_response.cookies
                        _LOGGER.info("Direct HTTP login successful")
                        return True
                    
                    # If we're still not logged in, try one more verification
                    async with new_session.get(
                        "https://www.bokat.se/myActivities.jsp",
                        cookies=login_response.cookies
                    ) as verify_response:
                        _LOGGER.debug("Verification response status: %s", verify_response.status)
                        
                        if verify_response.status == 200:
                            verify_html = await verify_response.text()
                            if "Logga in" not in verify_html and "login.jsp" not in verify_html:
                                # Copy all cookies to our main session
                                self._cookies = verify_response.cookies
                                _LOGGER.info("Direct HTTP login verified with activities page")
                                return True
            
            _LOGGER.error("Direct HTTP login method failed")
            return False
        except Exception as err:
            _LOGGER.error("Error in direct HTTP login to Bokat.se: %s", err)
            return False
    
    async def _login_final_fallback(self) -> bool:
        """Final fallback login method that tries a completely different approach."""
        try:
            _LOGGER.debug("Attempting final fallback login to Bokat.se")
            
            # Create a completely new session with specific settings
            timeout = aiohttp.ClientTimeout(total=30)  # Longer timeout
            conn = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification
            
            async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
                # Step 1: Visit the main page first
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",  # Swedish locale
                }
                
                # Try to access the site directly
                async with session.get("https://www.bokat.se/", headers=headers) as main_response:
                    _LOGGER.debug("Main page status: %s", main_response.status)
                    
                    # Store cookies
                    cookies = main_response.cookies
                    
                    # Check if we're already logged in (unlikely but possible)
                    main_html = await main_response.text()
                    if "Logga ut" in main_html and self._username in main_html:
                        _LOGGER.info("Already logged in on main page")
                        self._cookies = cookies
                        return True
                
                # Step 2: Try a direct login with a different URL
                login_data = {
                    "username": self._username,
                    "password": self._password,
                    "login": "Logga in",
                    "redirect": "index.jsp"  # Try adding a redirect parameter
                }
                
                # Try different login URLs
                login_urls = [
                    "https://www.bokat.se/login.jsp",
                    "https://www.bokat.se/login",
                    "https://www.bokat.se/j_security_check",
                    "https://www.bokat.se/j_spring_security_check"
                ]
                
                for login_url in login_urls:
                    try:
                        _LOGGER.debug("Trying login URL: %s", login_url)
                        
                        # Add specific headers for this request
                        login_headers = headers.copy()
                        login_headers.update({
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Referer": "https://www.bokat.se/login.jsp",
                            "Origin": "https://www.bokat.se",
                            "Cache-Control": "no-cache",
                            "Pragma": "no-cache"
                        })
                        
                        async with session.post(
                            login_url,
                            data=login_data,
                            headers=login_headers,
                            cookies=cookies,
                            allow_redirects=True
                        ) as login_response:
                            _LOGGER.debug("Login response status: %s for URL %s", login_response.status, login_url)
                            
                            # Update cookies
                            for key, value in login_response.cookies.items():
                                cookies[key] = value
                            
                            # Check if login was successful
                            response_html = await login_response.text()
                            
                            # Check for success indicators
                            if "Logga ut" in response_html or "Mina aktiviteter" in response_html:
                                self._cookies = cookies
                                _LOGGER.info("Fallback login successful with URL: %s", login_url)
                                return True
                            
                            # If we're redirected away from login, we might be logged in
                            if "login.jsp" not in str(login_response.url) and "Logga in" not in response_html:
                                # Verify with activities page
                                async with session.get(
                                    "https://www.bokat.se/myActivities.jsp",
                                    headers=headers,
                                    cookies=cookies
                                ) as verify_response:
                                    if verify_response.status == 200:
                                        verify_html = await verify_response.text()
                                        if "Logga in" not in verify_html:
                                            self._cookies = cookies
                                            _LOGGER.info("Fallback login verified with URL: %s", login_url)
                                            return True
                    except Exception as e:
                        _LOGGER.warning("Error with login URL %s: %s", login_url, e)
                
                # If all login URLs failed, try one more approach - direct access to activities
                try:
                    async with session.get(
                        "https://www.bokat.se/myActivities.jsp",
                        headers=headers,
                        cookies=cookies
                    ) as activities_response:
                        if activities_response.status == 200:
                            activities_html = await activities_response.text()
                            if "Logga in" not in activities_html and "login.jsp" not in activities_html:
                                self._cookies = cookies
                                _LOGGER.info("Fallback login successful with direct activities access")
                                return True
                except Exception as e:
                    _LOGGER.warning("Error accessing activities page: %s", e)
            
            _LOGGER.error("Final fallback login method failed")
            return False
        except Exception as err:
            _LOGGER.error("Error in fallback login to Bokat.se: %s", err)
            return False
    
    async def get_activities(self) -> list[dict]:
        """Get all activities from Bokat.se."""
        if not self._cookies:
            if not await self.login():
                raise ConfigEntryAuthFailed("Failed to authenticate with Bokat.se")
        
        try:
            async with async_timeout.timeout(10):
                response = await self._session.get(
                    "https://www.bokat.se/myActivities.jsp",
                    cookies=self._cookies,
                )
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Check if we're still logged in
                    if "Logga in" in html or "login.jsp" in html:
                        _LOGGER.debug("Session expired, trying to log in again")
                        if not await self.login():
                            raise ConfigEntryAuthFailed("Failed to re-authenticate with Bokat.se")
                        
                        # Try again with new cookies
                        response = await self._session.get(
                            "https://www.bokat.se/myActivities.jsp",
                            cookies=self._cookies,
                        )
                        
                        if response.status == 200:
                            html = await response.text()
                        else:
                            _LOGGER.error("Failed to get activities after re-login: %s", response.status)
                            return []
                    
                    # Parse activities from HTML
                    activities = self._parse_activities(html)
                    
                    # If we didn't find any activities, try using BeautifulSoup for more robust parsing
                    if not activities:
                        _LOGGER.debug("No activities found with regex, trying BeautifulSoup")
                        try:
                            soup = BeautifulSoup(html, 'html.parser')
                            activities = self._parse_activities_with_soup(soup)
                        except Exception as e:
                            _LOGGER.warning("Error parsing with BeautifulSoup: %s", e)
                    
                    return activities
                else:
                    _LOGGER.error("Failed to get activities: %s", response.status)
                    return []
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error getting activities: %s", err)
            return []
            
    def _parse_activities_with_soup(self, soup: BeautifulSoup) -> list[dict]:
        """Parse activities from HTML using BeautifulSoup."""
        activities = []
        
        # Look for activity tables
        tables = soup.find_all('table')
        for table in tables:
            # Look for rows with links to activities
            rows = table.find_all('tr')
            for row in rows:
                links = row.find_all('a')
                for link in links:
                    href = link.get('href')
                    if href and ('stat.jsp' in href or 'eventId' in href):
                        name = link.text.strip()
                        
                        # Try to find status in the same row
                        status_cell = row.find('td', class_='status')
                        status = status_cell.text.strip() if status_cell else "Unknown"
                        
                        # If no status cell with class, try the second td
                        if not status_cell:
                            cells = row.find_all('td')
                            if len(cells) >= 2:
                                status = cells[1].text.strip()
                        
                        # Clean up the URL
                        url = href
                        if not url.startswith('http'):
                            url = f"https://www.bokat.se/{url}"
                        
                        activities.append({
                            "name": name,
                            "status": status,
                            "url": url,
                        })
        
        return activities
    
    def _parse_activities(self, html: str) -> list[dict]:
        """Parse activities from HTML."""
        # This is a simplified example. In a real implementation,
        # you would use a proper HTML parser like BeautifulSoup.
        activities = []
        
        # Example pattern to match activity rows
        import re
        pattern = r'<tr[^>]*>.*?<a href="([^"]+)"[^>]*>([^<]+)</a>.*?<td[^>]*>([^<]+)</td>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for match in matches:
            url, name, status = match
            
            # Clean up the data
            url = f"https://www.bokat.se/{url}" if not url.startswith("http") else url
            name = name.strip()
            status = status.strip()
            
            activities.append({
                "name": name,
                "status": status,
                "url": url,
            })
        
        return activities
    
    async def get_activity_details(self, activity_url: str) -> dict:
        """Get details for a specific activity."""
        if not self._cookies:
            if not await self.login():
                raise ConfigEntryAuthFailed("Failed to authenticate with Bokat.se")
        
        try:
            async with async_timeout.timeout(10):
                response = await self._session.get(
                    activity_url,
                    cookies=self._cookies,
                )
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Check if we're still logged in
                    if "Logga in" in html or "login.jsp" in html:
                        _LOGGER.debug("Session expired, trying to log in again")
                        if not await self.login():
                            raise ConfigEntryAuthFailed("Failed to re-authenticate with Bokat.se")
                        
                        # Try again with new cookies
                        response = await self._session.get(
                            activity_url,
                            cookies=self._cookies,
                        )
                        
                        if response.status == 200:
                            html = await response.text()
                        else:
                            _LOGGER.error("Failed to get activity details after re-login: %s", response.status)
                            return {}
                    
                    # Parse activity details from HTML
                    details = self._parse_activity_details(html, activity_url)
                    
                    # If we didn't get much data, try using BeautifulSoup for more robust parsing
                    if not details.get("participants") and not details.get("name", "Unknown") == "Unknown":
                        _LOGGER.debug("No participants found with regex, trying BeautifulSoup")
                        try:
                            soup = BeautifulSoup(html, 'html.parser')
                            details = self._parse_activity_details_with_soup(soup, activity_url, details)
                        except Exception as e:
                            _LOGGER.warning("Error parsing details with BeautifulSoup: %s", e)
                    
                    return details
                else:
                    _LOGGER.error("Failed to get activity details: %s", response.status)
                    return {}
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error getting activity details: %s", err)
            return {}
            
    def _parse_activity_details(self, html: str, activity_url: str) -> dict:
        """Parse activity details from HTML."""
        # This is a simplified example. In a real implementation,
        # you would use a proper HTML parser like BeautifulSoup.
        details = {
            "name": "Unknown",
            "status": "Unknown",
            "url": activity_url,
            "participants": [],
            "total_participants": 0,
            "attending_count": 0,
            "not_attending_count": 0,
            "no_response_count": 0,
            "answer_url": "",
        }
        
        # Extract activity name
        import re
        name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if name_match:
            details["name"] = name_match.group(1).strip()
        
        # Extract status
        status_match = re.search(r'<div[^>]*class="status"[^>]*>([^<]+)</div>', html)
        if status_match:
            details["status"] = status_match.group(1).strip()
        
        # Extract answer URL
        answer_match = re.search(r'<a href="([^"]+)"[^>]*>Svara</a>', html)
        if answer_match:
            answer_url = answer_match.group(1)
            details["answer_url"] = f"https://www.bokat.se/{answer_url}" if not answer_url.startswith("http") else answer_url
        
        # Extract participants
        participant_pattern = r'<tr[^>]*>.*?<td[^>]*>([^<]+)</td>.*?<td[^>]*>([^<]+)</td>.*?<td[^>]*>([^<]*)</td>.*?<td[^>]*>([^<]*)</td>'
        participant_matches = re.findall(participant_pattern, html, re.DOTALL)
        
        participants = []
        attending_count = 0
        not_attending_count = 0
        no_response_count = 0
        
        for match in participant_matches:
            name, status_text, comment, timestamp = [m.strip() for m in match]
            
            # Map status text to status code
            if "Kommer" in status_text:
                status = "yes"
                attending_count += 1
                
                # Extract guest count if available
                guest_match = re.search(r'\+\s*(\d+)', status_text)
                guests = int(guest_match.group(1)) if guest_match else 0
            elif "Kommer inte" in status_text:
                status = "no"
                not_attending_count += 1
                guests = 0
            elif "Endast kommentar" in status_text:
                status = "comment_only"
                not_attending_count += 1  # Count as not attending
                guests = 0
            else:
                status = "no_response"
                no_response_count += 1
                guests = 0
            
            participants.append({
                "name": name,
                "status": status,
                "comment": comment,
                "timestamp": timestamp,
                "guests": guests
            })
        
        details["participants"] = participants
        details["total_participants"] = len(participants)
        details["attending_count"] = attending_count
        details["not_attending_count"] = not_attending_count
        details["no_response_count"] = no_response_count
        
        return details
    
    def _parse_activity_details_with_soup(self, soup: BeautifulSoup, activity_url: str, existing_details: dict = None) -> dict:
        """Parse activity details from HTML using BeautifulSoup."""
        details = existing_details or {
            "name": "Unknown",
            "status": "Unknown",
            "url": activity_url,
            "participants": [],
            "total_participants": 0,
            "attending_count": 0,
            "not_attending_count": 0,
            "no_response_count": 0,
            "answer_url": "",
        }
        
        # Extract activity name from h1 or title
        h1 = soup.find('h1')
        if h1:
            details["name"] = h1.text.strip()
        else:
            title = soup.find('title')
            if title:
                title_text = title.text.strip()
                # Remove "Bokat.se - " prefix if present
                if " - " in title_text:
                    details["name"] = title_text.split(" - ", 1)[1]
                else:
                    details["name"] = title_text
        
        # Extract status from div with class status
        status_div = soup.find('div', class_='status')
        if status_div:
            details["status"] = status_div.text.strip()
        
        # Extract answer URL
        answer_link = soup.find('a', text='Svara')
        if answer_link:
            answer_url = answer_link.get('href')
            if answer_url:
                details["answer_url"] = f"https://www.bokat.se/{answer_url}" if not answer_url.startswith("http") else answer_url
        
        # Extract participants from table
        participant_tables = soup.find_all('table')
        participants = []
        attending_count = 0
        not_attending_count = 0
        no_response_count = 0
        
        for table in participant_tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:  # Name, status, comment, timestamp
                    name_cell = cells[0]
                    status_cell = cells[1]
                    comment_cell = cells[2]
                    timestamp_cell = cells[3] if len(cells) > 3 else None
                    
                    name = name_cell.text.strip()
                    status_text = status_cell.text.strip()
                    comment = comment_cell.text.strip() if comment_cell else ""
                    timestamp = timestamp_cell.text.strip() if timestamp_cell else ""
                    
                    # Skip header rows
                    if name.lower() in ["namn", "name"] or status_text.lower() in ["status"]:
                        continue
                    
                    # Map status text to status code
                    if "Kommer" in status_text:
                        status = "yes"
                        attending_count += 1
                        
                        # Extract guest count if available
                        guest_match = re.search(r'\+\s*(\d+)', status_text)
                        guests = int(guest_match.group(1)) if guest_match else 0
                    elif "Kommer inte" in status_text:
                        status = "no"
                        not_attending_count += 1
                        guests = 0
                    elif "Endast kommentar" in status_text:
                        status = "comment_only"
                        not_attending_count += 1  # Count as not attending
                        guests = 0
                    else:
                        status = "no_response"
                        no_response_count += 1
                        guests = 0
                    
                    participants.append({
                        "name": name,
                        "status": status,
                        "comment": comment,
                        "timestamp": timestamp,
                        "guests": guests
                    })
        
        # Only update participants if we found any
        if participants:
            details["participants"] = participants
            details["total_participants"] = len(participants)
            details["attending_count"] = attending_count
            details["not_attending_count"] = not_attending_count
            details["no_response_count"] = no_response_count
        
        return details
    
    async def submit_response(self, activity_url: str, attendance: str, guests: int = 0, comment: str = "") -> bool:
        """Submit a response to an activity."""
        if not self._cookies:
            if not await self.login():
                raise ConfigEntryAuthFailed("Failed to authenticate with Bokat.se")
        
        # Extract event ID and user ID from URL
        # Example URL: https://www.bokat.se/stat.jsp?eventId=12345&userId=67890
        import re
        match = re.search(r"eventId=(\d+)&userId=(\d+)", activity_url)
        if not match:
            _LOGGER.error("Invalid activity URL: %s", activity_url)
            return False
        
        event_id = match.group(1)
        user_id = match.group(2)
        
        # Map attendance to Bokat.se values
        attendance_value = {
            ATTENDANCE_YES: "yes",
            ATTENDANCE_NO: "no",
            ATTENDANCE_COMMENT_ONLY: "comment_only",
        }.get(attendance, "yes")
        
        try:
            # First, check if we need to get the answer form to extract any hidden fields
            form_data = {
                "eventId": event_id,
                "userId": user_id,
                "attendance": attendance_value,
                "guests": str(guests) if attendance == ATTENDANCE_YES else "0",
                "comment": comment,
                "submit": "Svara",
            }
            
            # Try to get the answer form first to check if we're still logged in
            answer_url = f"https://www.bokat.se/answer.jsp?eventId={event_id}&userId={user_id}"
            
            async with async_timeout.timeout(10):
                form_response = await self._session.get(
                    answer_url,
                    cookies=self._cookies,
                )
                
                if form_response.status == 200:
                    form_html = await form_response.text()
                    
                    # Check if we're still logged in
                    if "Logga in" in form_html or "login.jsp" in form_html:
                        _LOGGER.debug("Session expired, trying to log in again")
                        if not await self.login():
                            raise ConfigEntryAuthFailed("Failed to re-authenticate with Bokat.se")
                        
                        # Try again with new cookies
                        form_response = await self._session.get(
                            answer_url,
                            cookies=self._cookies,
                        )
                        
                        if form_response.status == 200:
                            form_html = await form_response.text()
                        else:
                            _LOGGER.error("Failed to get answer form after re-login: %s", form_response.status)
                            return False
                    
                    # Try to extract any hidden fields from the form
                    try:
                        soup = BeautifulSoup(form_html, 'html.parser')
                        form = soup.find('form')
                        if form:
                            hidden_fields = form.find_all('input', type='hidden')
                            for field in hidden_fields:
                                name = field.get('name')
                                value = field.get('value')
                                if name and value and name not in form_data:
                                    form_data[name] = value
                    except Exception as e:
                        _LOGGER.warning("Error extracting hidden fields: %s", e)
            
            # Now submit the response
            async with async_timeout.timeout(10):
                response = await self._session.post(
                    "https://www.bokat.se/answer.jsp",
                    data=form_data,
                    cookies=self._cookies,
                    allow_redirects=False,
                )
                
                # Check for both 302 (redirect) and 200 (success) responses
                if response.status == 302:  # Successful submission redirects
                    _LOGGER.debug("Successfully submitted response (302 redirect)")
                    return True
                elif response.status == 200:
                    # Check if the response indicates success
                    html = await response.text()
                    if "Tack för ditt svar" in html or "Thank you for your response" in html:
                        _LOGGER.debug("Successfully submitted response (200 with success message)")
                        return True
                    elif "Logga in" in html or "login.jsp" in html:
                        _LOGGER.error("Session expired during submission")
                        return False
                    else:
                        _LOGGER.error("Failed to submit response: %s", response.status)
                        return False
                else:
                    _LOGGER.error("Failed to submit response: %s", response.status)
                    return False
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error submitting response: %s", err)
            return False

class BokatDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Bokat.se."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        client: BokatApiClient,
        name: str,
        update_interval: timedelta,
        activity_url: Optional[str] = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=update_interval,
        )
        self.client = client
        self.activity_url = activity_url
        self.entity_id = None  # Will be set by the sensor
    
    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Bokat.se."""
        try:
            # Get all activities
            activities = await self.client.get_activities()
            
            # If no activity URL is set, use the first activity
            if not self.activity_url and activities:
                self.activity_url = activities[0]["url"]
            
            # Get details for the selected activity
            selected_activity = {}
            if self.activity_url:
                selected_activity = await self.client.get_activity_details(self.activity_url)
            
            return {
                "activities": activities,
                "selected_activity": selected_activity,
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Bokat.se: {err}") 
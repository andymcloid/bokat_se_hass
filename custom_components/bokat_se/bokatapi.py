"""BokatAPI module for interacting with bokat.se."""
from __future__ import annotations

import asyncio
import logging
import re
import sys
import json
from typing import Dict, List, Optional, Any

import aiohttp
from bs4 import BeautifulSoup

__version__ = "0.1.0"

_LOGGER = logging.getLogger(__name__)


class BokatAPI:
    """API client for Bokat.se."""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        """Initialize the API client.
        
        Args:
            session: Optional aiohttp ClientSession. If not provided, a new session will be created.
        """
        self._session = session
        self._own_session = session is None
        self._cookies = None
    
    async def __aenter__(self) -> "BokatAPI":
        """Async enter context manager."""
        if self._own_session:
            self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async exit context manager."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None
    
    async def _login(self, username: str, password: str) -> BeautifulSoup:
        """Log in to Bokat.se.
        
        Args:
            username: The username for Bokat.se
            password: The password for Bokat.se
            
        Returns:
            bool: True if login was successful, False otherwise
        """
        if not self._session:
            self._session = aiohttp.ClientSession()
            self._own_session = True
            
        # Initialize cookies dictionary if not already done
        if not self._cookies:
            self._cookies = {}
            
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        url = "https://www.bokat.se/userPage.jsp"

        try:
            _LOGGER.debug("Attempting to log in to Bokat.se with username: %s", username)
            
            # First, try to access the userPage.jsp to get any required cookies
            async with self._session.get(
                url=url,
                headers=headers,
                allow_redirects=True
            ) as home_response:
                
                # HTTP 200 OK?
                if not home_response.status == 200:
                    _LOGGER.error("Failed to load %s", url)
                    return None

                # Store initial cookies
                for cookie_name, cookie in home_response.cookies.items():
                    self._cookies[cookie_name] = cookie.value
                

                # Check if we can find the login form on the page
                home_html = await home_response.text()
                home_soup = BeautifulSoup(home_html, 'html.parser')
                login_form = home_soup.find('form', {'action': re.compile('userPage.jsp*')})

                if not login_form:
                    _LOGGER.error("Error. Coudn't load login form.")
                    return None
                        
                # Extract the input field names from the form
                email_field = login_form.find('input', {'name': 'e'})
                password_field = login_form.find('input', {'name': 'l'})

                # Return if we cant find the login form components
                if not email_field and not password_field:
                    _LOGGER.error("Could not find email or password fields in the form")
                    return None

                # Try direct login using the form we found
                async with self._session.post(
                    url=url,
                    data={
                        "e": username,
                        "l": password,
                    },
                    headers=headers,
                    cookies=self._cookies,
                    allow_redirects=True,
                ) as response:
                    
                    # Update cookies from response
                    for cookie_name, cookie in response.cookies.items():
                        self._cookies[cookie_name] = cookie.value
                    
                    # Log response status and URL
                    if not response.status == 200:
                        _LOGGER.error("Login failed. Status: %s", response.status)
                        return None
          
                    # Check the content
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Check for the specific header that indicates successful login
                    header = soup.find('h1', {'class': 'HeaderLarge'})
                    if header and 'Användarsida' in header.text:
                        _LOGGER.info("Login successful.")
                        return soup
                    else:
                        _LOGGER.error("Login failed.")
                        return None

        except Exception as e:
            _LOGGER.error("Error during login: %s", e)
            return None
                
    async def list_activities(self, username: str, password: str) -> List[Dict[str, str]]:
        """List all activities for the user.
        
        Args:
            username: The username for Bokat.se
            password: The password for Bokat.se
            
        Returns:
            List[Dict[str, str]]: A list of activities with name and URL
        """
        if not self._session:
            self._session = aiohttp.ClientSession()
            self._own_session = True

        # Always login to fetch the activity list
        soup = await self._login(username, password)

        if not soup:
            _LOGGER.error("Failed to authenticate with Bokat.se")
            return []
        
        test = self._parse_activities(soup)
        ## PLACE HOLDER FOR FINDING ALL GROUP NAMES + THEIR URLS STARTING WITH stat.jsp
        _LOGGER.debug(test)
        return []

    
    
    def _parse_activities(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Parse activities from HTML using BeautifulSoup.
        
        Args:
            soup: BeautifulSoup object with the HTML content
            
        Returns:
            List[Dict[str, str]]: A list of activities with name and URL
        """
        activities = []
        
        # First try to find activities in the userPage.jsp format (most common)
        _LOGGER.debug("Trying to parse activities in userPage.jsp format")
        
        # Look for the activities table with header "Aktiviteter"
        # Using find method instead of select with :contains to avoid deprecation warning
        activities_header = None
        for header in soup.find_all('th', class_='RowHeader'):
            if 'Aktiviteter' in header.text:
                activities_header = header
                break
                
        if activities_header:
            _LOGGER.debug("Found activities header")
            activities_table = activities_header.find_parent('table')
            if activities_table:
                _LOGGER.debug("Found activities table")
                
                # In userPage.jsp, activities are grouped in sets of rows
                # Each activity has multiple rows with different information
                rows = activities_table.select('tr')
                
                current_activity = {}
                for i, row in enumerate(rows):
                    # Skip the header row
                    if row.find('th', class_='RowHeader'):
                        continue
                    
                    # Check if this is a row with activity name
                    activity_link = row.select_one('a[href*="stat.jsp"]')
                    if activity_link:
                        # If we have a previous activity, add it to the list
                        if current_activity and 'name' in current_activity and 'url' in current_activity:
                            activities.append(current_activity)
                        
                        # Start a new activity
                        href = activity_link.get('href')
                        url = href
                        if not url.startswith('http'):
                            url = f"https://www.bokat.se/{url}"
                        
                        current_activity = {
                            "name": "",  # Will be filled from the activity row
                            "url": url,
                            "group": "",  # Will be filled if available
                            "date_time": "",  # Will be filled if available
                        }
                    
                    # Look for activity details in the cells
                    cells = row.select('td')
                    if len(cells) >= 2:
                        # Check for different types of information
                        label_cell = cells[1] if len(cells) > 1 else None
                        value_cell = cells[2] if len(cells) > 2 else None
                        
                        if label_cell and value_cell:
                            label_text = label_cell.text.strip()
                            value_text = value_cell.text.strip()
                            
                            if "Grupp" in label_text and current_activity:
                                current_activity["group"] = value_text
                            elif "Aktivitet" in label_text and current_activity:
                                current_activity["name"] = value_text
                            elif "Tid" in label_text and current_activity:
                                current_activity["date_time"] = value_text
                
                # Add the last activity if we have one
                if current_activity and 'name' in current_activity and 'url' in current_activity:
                    activities.append(current_activity)
        
        # If we found activities in the userPage.jsp format, return them
        if activities:
            _LOGGER.debug("Found %d activities in userPage.jsp format", len(activities))
            return activities
        
        # If no activities found in userPage.jsp format, try other formats
        
        # Try to find activities in the main content area
        content_div = soup.select_one('#content, .content, main')
        if content_div:
            _LOGGER.debug("Found main content area, searching for activities")
            
            # Look for activity links directly
            activity_links = content_div.select('a[href*="stat.jsp"], a[href*="eventId"]')
            for link in activity_links:
                name = link.text.strip()
                href = link.get('href')
                
                # Skip empty links or non-activity links
                if not name or not href:
                    continue
                
                # Clean up the URL
                url = href
                if not url.startswith('http'):
                    url = f"https://www.bokat.se/{url}"
                
                _LOGGER.debug("Found activity: %s at %s", name, url)
                activities.append({
                    "name": name,
                    "url": url,
                })
        
        # If we didn't find activities in the content area, try tables
        if not activities:
            _LOGGER.debug("No activities found in content area, searching tables")
            
            # Look for activity tables - more specific selector
            tables = soup.select('table.activities, table.events, table.list, table')
            _LOGGER.debug("Found %d tables in the HTML", len(tables))
            
            for i, table in enumerate(tables):
                # Look for rows with links to activities
                rows = table.select('tr')
                _LOGGER.debug("Table %d: Found %d rows", i+1, len(rows))
                
                for row in rows:
                    links = row.select('a[href*="stat.jsp"], a[href*="eventId"]')
                    for link in links:
                        name = link.text.strip()
                        href = link.get('href')
                        
                        # Skip empty links
                        if not name or not href:
                            continue
                        
                        # Clean up the URL
                        url = href
                        if not url.startswith('http'):
                            url = f"https://www.bokat.se/{url}"
                        
                        _LOGGER.debug("Found activity: %s at %s", name, url)
                        activities.append({
                            "name": name,
                            "url": url,
                        })
        
        # If we still didn't find activities, try a more general approach
        if not activities:
            _LOGGER.debug("No activities found in tables, trying general approach")
            
            # Look for any links that might be activities
            all_links = soup.select('a[href*="stat.jsp"], a[href*="eventId"]')
            for link in all_links:
                name = link.text.strip()
                href = link.get('href')
                
                # Skip empty links
                if not name or not href:
                    continue
                
                # Clean up the URL
                url = href
                if not url.startswith('http'):
                    url = f"https://www.bokat.se/{url}"
                
                _LOGGER.debug("Found activity: %s at %s", name, url)
                activities.append({
                    "name": name,
                    "url": url,
                })
        
        # Try to find activities in the app format
        if not activities:
            _LOGGER.debug("No activities found in standard formats, trying app format")
            
            # Look for activity cards or list items
            activity_items = soup.select('.activity-item, .event-item, .card, .list-item')
            if activity_items:
                _LOGGER.debug("Found %d activity items", len(activity_items))
                
                for item in activity_items:
                    # Try to find the activity name and link
                    link = item.select_one('a')
                    if not link:
                        continue
                    
                    name = link.text.strip()
                    href = link.get('href')
                    
                    # Skip empty links
                    if not name or not href:
                        continue
                    
                    # Clean up the URL
                    url = href
                    if not url.startswith('http'):
                        url = f"https://www.bokat.se/{url}"
                    
                    _LOGGER.debug("Found activity: %s at %s", name, url)
                    activities.append({
                        "name": name,
                        "url": url,
                    })
            
            # Try to find activities in a JSON script tag
            script_tags = soup.select('script')
            for script in script_tags:
                script_text = script.string
                if not script_text:
                    continue
                
                # Look for JSON data in the script
                if 'activities' in script_text or 'events' in script_text:
                    _LOGGER.debug("Found script with potential activity data")
                    
                    try:
                        # Try to extract JSON data
                        json_start = script_text.find('{')
                        json_end = script_text.rfind('}') + 1
                        
                        if json_start >= 0 and json_end > json_start:
                            json_data = script_text[json_start:json_end]
                            data = json.loads(json_data)
                            
                            # Look for activities or events in the data
                            if 'activities' in data:
                                _LOGGER.debug("Found activities in JSON data")
                                for activity in data['activities']:
                                    if 'name' in activity and 'url' in activity:
                                        activities.append(activity)
                                    elif 'name' in activity and 'id' in activity:
                                        url = f"https://www.bokat.se/stat.jsp?eventId={activity['id']}"
                                        activities.append({
                                            "name": activity['name'],
                                            "url": url,
                                        })
                            elif 'events' in data:
                                _LOGGER.debug("Found events in JSON data")
                                for event in data['events']:
                                    if 'name' in event and 'url' in event:
                                        activities.append(event)
                                    elif 'name' in event and 'id' in event:
                                        url = f"https://www.bokat.se/stat.jsp?eventId={event['id']}"
                                        activities.append({
                                            "name": event['name'],
                                            "url": url,
                                        })
                    except Exception as e:
                        _LOGGER.debug("Error parsing JSON data: %s", e)
        
        if not activities:
            _LOGGER.warning("No activities found in the HTML")
            # Log the entire HTML for debugging
            _LOGGER.debug("HTML content: %s", soup.prettify())
        
        return activities
    

# Convenience functions
async def list_activities(username: str, password: str) -> List[Dict[str, str]]:
    """List all activities for the user.
    
    Args:
        username: The username for Bokat.se
        password: The password for Bokat.se
        
    Returns:
        List[Dict[str, str]]: A list of activities with name and URL
    """
    async with BokatAPI() as api:
        return await api.list_activities(username, password)


# Command line interface
async def main():
    """Run the command line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="BokatAPI command line interface")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List activities command
    list_parser = subparsers.add_parser("list", help="List activities")
    list_parser.add_argument("username", help="Username for Bokat.se")
    list_parser.add_argument("password", help="Password for Bokat.se")
    
    # Get activity command
    get_parser = subparsers.add_parser("get", help="Get activity details")
    get_parser.add_argument("url", help="URL of the activity")
    
    args = parser.parse_args()
    
    if args.command == "list":
        activities = await list_activities(args.username, args.password)
        print(json.dumps(activities, indent=2, ensure_ascii=False))
    elif args.command == "get":
        activity = await get_activity(args.url)
        print(json.dumps(activity, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Run the main function
    asyncio.run(main()) 
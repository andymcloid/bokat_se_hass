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
    base_url = "https://www.bokat.se/"
    
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
        url = self.base_url + "userPage.jsp"

        try:
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
                        _LOGGER.info("Login successful for %s", username)
                        return soup
                    else:
                        _LOGGER.error("Login failed for %s", username)
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
        
        activities = self._parse_activities(soup)
        return activities

    def _parse_activities(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Parse activities from HTML using BeautifulSoup.
        
        Args:
            soup: BeautifulSoup object with the HTML content
            
        Returns:
            List[Dict[str, str]]: A list of activities with name, URL, eventId, userId, and group
        """
        activities = []
        
        # Create a mapping of all activity names and their rows
        activity_data = {}
        
        # First pass: find all group names
        group_names = {}
        current_group = None
        
        for row in soup.find_all('tr'):
            # Look for group name
            for td in row.find_all('td'):
                b_tag = td.find('b')
                if not b_tag or "Grupp:" not in b_tag.text:
                    continue
                    
                next_td = td.find_next_sibling('td')
                if not next_td:
                    continue
                    
                current_group = next_td.text.strip()
                # Store the row index for reference
                group_names[row] = current_group
        
        # Second pass: find all activity names and associate with groups
        for row in soup.find_all('tr'):
            # Look for activity name
            for td in row.find_all('td'):
                b_tag = td.find('b')
                if not b_tag or "Aktivitet:" not in b_tag.text:
                    continue
                    
                next_td = td.find_next_sibling('td')
                if not next_td:
                    continue
                    
                # Get the activity name
                activity_name = next_td.text.strip()
                if not activity_name:
                    continue
                
                # Find the closest group name by looking at previous rows
                closest_group = None
                current_row = row
                
                # Look back up to 10 rows to find the group name
                for _ in range(10):
                    prev_row = current_row.find_previous_sibling('tr')
                    if not prev_row:
                        break
                        
                    if prev_row in group_names:
                        closest_group = group_names[prev_row]
                        break
                        
                    current_row = prev_row
                
                # Store activity data with group name
                activity_data[activity_name] = {
                    "name": activity_name,
                    "group": closest_group or "Unknown Group"
                }
                # Store the row for later reference
                activity_data[activity_name]["row"] = row
        
        # Third pass: find all stat.jsp links and extract eventId and userId
        for row in soup.find_all('tr'):
            link = row.find('a', href=lambda href: href and 'stat.jsp' in href)
            if not link:
                continue
                
            href = link.get('href')
            
            # Extract eventId and userId from URL
            event_id = None
            user_id = None
            
            # Parse URL parameters
            if href:
                # Extract eventId
                event_id_match = re.search(r'eventId=(\d+)', href)
                if event_id_match:
                    event_id = event_id_match.group(1)
                
                # Extract userId
                user_id_match = re.search(r'userId=(\d+)', href)
                if user_id_match:
                    user_id = user_id_match.group(1)
            
            # Ensure URL is properly formatted with base URL
            if href and not href.startswith('http'):
                if href.startswith('/'):
                    href = f"{self.base_url.rstrip('/')}{href}"
                else:
                    href = f"{self.base_url}{href}"
            
            # Find the closest activity name
            closest_activity = None
            min_distance = float('inf')
            
            for name, data in activity_data.items():
                # Calculate distance between rows (approximate)
                try:
                    name_row = data["row"]
                    name_index = list(soup.find_all('tr')).index(name_row)
                    link_index = list(soup.find_all('tr')).index(row)
                    distance = abs(link_index - name_index)
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_activity = name
                except ValueError:
                    continue
            
            # If we found a close activity name and the distance is reasonable
            if closest_activity and min_distance < 15:  # Adjust threshold as needed
                # Get the activity data
                activity = activity_data[closest_activity].copy()
                
                # Add URL, eventId, and userId
                activity["url"] = href
                activity["eventId"] = event_id
                activity["userId"] = user_id
                
                # Remove the row reference before adding to results
                activity.pop("row", None)
                
                activities.append(activity)
                
                # Remove this activity from the mapping to avoid duplicates
                activity_data.pop(closest_activity, None)
        
        if not activities:
            _LOGGER.warning("No activities found in the HTML")
        else:
            activity_names_list = [activity["name"] for activity in activities]
            _LOGGER.info("Found %d activities: %s", len(activities), ", ".join(activity_names_list))
            
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
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
        
        # First pass: find all activity names and their groups
        activity_names = []
        activity_groups = {}
        
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
                
                # Add to our list of activities in order
                if activity_name not in activity_names:
                    activity_names.append(activity_name)
            
            # Look for group name
            for td in row.find_all('td'):
                b_tag = td.find('b')
                if not b_tag or "Grupp:" not in b_tag.text:
                    continue
                    
                next_td = td.find_next_sibling('td')
                if not next_td:
                    continue
                    
                group_name = next_td.text.strip()
                
                # Associate with the most recently found activity
                if activity_names and activity_names[-1] not in activity_groups:
                    activity_groups[activity_names[-1]] = group_name
        
        # Second pass: find all stat.jsp links in order
        stat_links = []
        for link in soup.find_all('a', href=lambda href: href and 'stat.jsp' in href):
            href = link.get('href')
            if href:
                # Ensure URL is properly formatted with base URL
                if not href.startswith('http'):
                    if href.startswith('/'):
                        href = f"{self.base_url.rstrip('/')}{href}"
                    else:
                        href = f"{self.base_url}{href}"
                
                # Extract eventId and userId
                event_id = None
                user_id = None
                
                event_id_match = re.search(r'eventId=(\d+)', href)
                if event_id_match:
                    event_id = event_id_match.group(1)
                
                user_id_match = re.search(r'userId=(\d+)', href)
                if user_id_match:
                    user_id = user_id_match.group(1)
                
                stat_links.append({
                    "url": href,
                    "eventId": event_id,
                    "userId": user_id
                })
        
        # Log what we found
        _LOGGER.info("Found %d activity names: %s", len(activity_names), ", ".join(activity_names))
        _LOGGER.info("Found %d stat.jsp links", len(stat_links))
        
        # Match activities with links in order
        for i, activity_name in enumerate(activity_names):
            if i < len(stat_links):
                link_data = stat_links[i]
                
                activity = {
                    "name": activity_name,
                    "group": activity_groups.get(activity_name, "Unknown Group"),
                    "url": link_data["url"],
                    "eventId": link_data["eventId"],
                    "userId": link_data["userId"]
                }
                
                activities.append(activity)
        
        if not activities:
            _LOGGER.warning("No activities found in the HTML")
        else:
            activity_names_list = [activity["name"] for activity in activities]
            _LOGGER.info("Found %d activities: %s", len(activities), ", ".join(activity_names_list))
            
        return activities
    
    async def get_activity_info(self, event_id: str) -> Dict[str, Any]:
        """Get detailed information about an activity.
        
        Args:
            event_id: The ID of the event to get information for
            
        Returns:
            Dict[str, Any]: Activity information including participants
        """
        url = f"{self.base_url}statPrint.jsp?eventId={event_id}"
        
        _LOGGER.info("Fetching activity info for event ID %s", event_id)
        
        async with self._session.get(url, cookies=self._cookies) as response:
            if response.status != 200:
                _LOGGER.error("Failed to get activity info: %s", response.status)
                return {
                    "error": f"Failed to get activity info: {response.status}",
                    "attendees": 0,
                    "no_reply": 0,
                    "rejects": 0,
                    "participants": []
                }
            
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            
            return self._parse_activity_info(soup)
    
    def _parse_activity_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse activity information from HTML using BeautifulSoup.
        
        Args:
            soup: BeautifulSoup object with the HTML content
            
        Returns:
            Dict[str, Any]: Activity information including participants
        """
        result = {
            "name": "",
            "attendees": 0,
            "no_reply": 0,
            "rejects": 0,
            "guests": 0,
            "participants": []
        }
        
        # Get activity name from h1 tag
        h1 = soup.find('h1')
        if h1:
            result["name"] = h1.text.strip()
        
        # Parse summary information
        summary_text = ""
        summary = soup.find('td', align='center', text=lambda t: t and 'Sammanställning' in t)
        if summary:
            summary_text = summary.text.strip()
            
            # Extract numbers from summary
            invited_match = re.search(r'Av\s+<b>(\d+)</b>\s+inbjudna', str(summary))
            yes_match = re.search(r'har\s+<b>(\d+)</b>\s+tackat\s+ja', str(summary))
            no_match = re.search(r'<b>(\d+)</b>\s+nej', str(summary))
            no_reply_match = re.search(r'och\s+<b>(\d+)</b>\s+har\s+inte\s+svarat', str(summary))
            guests_match = re.search(r'<b>(\d+)</b>\s+gäster/extra', str(summary))
            
            if invited_match:
                result["invited"] = int(invited_match.group(1))
            if yes_match:
                result["attendees"] = int(yes_match.group(1))
            if no_match:
                result["rejects"] = int(no_match.group(1))
            if no_reply_match:
                result["no_reply"] = int(no_reply_match.group(1))
            if guests_match:
                result["guests"] = int(guests_match.group(1))
        
        # Parse participants
        participants = []
        
        # Find the table with participants
        participant_table = soup.find('table', {'class': 'Text', 'width': '710'})
        if participant_table:
            rows = participant_table.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                # Skip header row
                if cells[0].find('th'):
                    continue
                
                # Skip separator rows
                if 'cell' in cells[0].get('id', ''):
                    continue
                
                # Get status
                status_cell = cells[0].find('table')
                status = "NoReply"
                if status_cell:
                    status_text = status_cell.text.strip()
                    if "Ja!" in status_text:
                        status = "Attending"
                    elif "Nej!" in status_text:
                        status = "NotAttending"
                    elif status_text.strip() == "":
                        # Check if there's a comment but no yes/no
                        comment_cell = cells[3].text.strip()
                        if comment_cell and comment_cell != "&nbsp;":
                            status = "OnlyComment"
                        else:
                            status = "NoReply"
                
                # Get name and timestamp
                name_cell = cells[1].text.strip()
                name = name_cell
                timestamp = ""
                
                # Extract timestamp if present (format: "Name\n(YYYY-MM-DD HH:MM)")
                timestamp_match = re.search(r'(.*?)(?:\s*\n\s*\((.*?)\))?$', name_cell, re.DOTALL)
                if timestamp_match:
                    name = timestamp_match.group(1).strip()
                    if timestamp_match.group(2):
                        timestamp = timestamp_match.group(2).strip()
                
                # Get guests
                guests = 0
                guests_cell = cells[2].text.strip()
                if guests_cell and guests_cell != "&nbsp;":
                    guests_match = re.search(r'\+(\d+)', guests_cell)
                    if guests_match:
                        guests = int(guests_match.group(1))
                
                # Get comment
                comment = cells[3].text.strip()
                if comment == "&nbsp;":
                    comment = ""
                
                participant = {
                    "name": name,
                    "timestamp": timestamp,
                    "status": status,
                    "comment": comment,
                    "guests": guests
                }
                
                participants.append(participant)
        
        result["participants"] = participants
        
        _LOGGER.info("Parsed activity info for '%s': %d attendees, %d rejects, %d no reply, %d guests", 
                    result["name"], result["attendees"], result["rejects"], 
                    result["no_reply"], result["guests"])
        
        return result

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
    
async def get_activity_info(event_id: str) -> List[Dict[str, Any]]:
    """Get detailed information about an activity.
    
    Args:
        event_id: The ID of the event to get information for
        
    Returns:
        Dict[str, Any]: Activity information including participants
    """
    async with BokatAPI() as api:
        return await api.get_activity_info(event_id)



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
"""BokatAPI module for interacting with bokat.se."""
from __future__ import annotations

import logging
import re
import json
from typing import Dict, List, Optional, Any

import aiohttp
from bs4 import BeautifulSoup

__version__ = "0.1.0"

_LOGGER = logging.getLogger(__name__)


class BokatAPI:

    """API client for Bokat.se."""
    base_url = "https://www.bokat.se/"
    

    """Private Functions"""

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
        activity_times = {}
        
        # Track the current group name as we scan through rows
        current_group = None
        current_time = None
        
        # Scan through all rows in order
        for row in soup.find_all('tr'):
            # Check for group name
            group_td = row.find('td', text=lambda t: t and 'Grupp:' in t)
            if group_td:
                next_td = group_td.find_next_sibling('td')
                if next_td:
                    current_group = next_td.text.strip()
                    # _LOGGER.debug("Found group: %s", current_group)
            
            # Check for time information
            time_td = row.find('td', text=lambda t: t and 'Tid:' in t)
            if time_td:
                next_td = time_td.find_next_sibling('td')
                if next_td:
                    current_time = next_td.text.strip()
                    # _LOGGER.debug("Found time: %s", current_time)
            
            # Check for activity name
            activity_td = row.find('td', text=lambda t: t and 'Aktivitet:' in t)
            if activity_td:
                next_td = activity_td.find_next_sibling('td')
                if next_td:
                    activity_name = next_td.text.strip()
                    if activity_name and activity_name not in activity_names:
                        activity_names.append(activity_name)
                        if current_group:
                            activity_groups[activity_name] = current_group
                        if current_time:
                            activity_times[activity_name] = current_time
                        # _LOGGER.debug("Found activity: %s (Group: %s, Time: %s)", activity_name, current_group or "Unknown", current_time or "Unknown")
        
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
        for name in activity_names:
            # _LOGGER.info("Activity '%s' has group '%s' and time '%s'", name, activity_groups.get(name, "Unknown Group"), activity_times.get(name, "Unknown Time"))
            pass
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
                
                # Add time information if available
                if activity_name in activity_times:
                    activity["time"] = activity_times.get(activity_name)
                
                activities.append(activity)
        
        if not activities:
            _LOGGER.warning("No activities found in the HTML")
        else:
            activity_names_list = [activity["name"] for activity in activities]
            _LOGGER.info("Found %d activities: %s", len(activities), ", ".join(activity_names_list))
            
        return activities

    def _parse_activity_info(self, html: str) -> Dict[str, Any]:
        """Parse activity information directly from HTML string.
        
        Args:
            html: HTML content as string
            
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
        
        # Get activity name
        name_match = re.search(r'<h1>(.*?)</h1>', html)
        if name_match:
            result["name"] = name_match.group(1).strip()
        
        # Parse summary information
        summary_match = re.search(r'Sammanställning:</b>\s*Av\s*<b>(\d+)</b>\s*inbjudna\s*har\s*<b>(\d+)</b>\s*tackat\s*ja,\s*<b>(\d+)</b>\s*nej\s*och\s*<b>(\d+)</b>\s*har\s*inte\s*svarat', html)
        if summary_match:
            result["invited"] = int(summary_match.group(1))
            result["attendees"] = int(summary_match.group(2))
            result["rejects"] = int(summary_match.group(3))
            result["no_reply"] = int(summary_match.group(4))
        
        # Parse guests count
        guests_match = re.search(r'<b>(\d+)</b>\s*gäster/extra', html)
        if guests_match:
            result["guests"] = int(guests_match.group(1))
        
        # Parse participants
        participants = []
        
        # Split the HTML into rows
        rows = html.split('<tr>')
        
        for row in rows:
            # Check if this is a participant row
            if '<td class="TextSmall" align="left">' not in row:
                continue
            
            # Extract status
            status = "NoReply"
            if '<font color="green">Ja!' in row:
                status = "Attending"
            elif '<font color="red">Nej!' in row:
                status = "NotAttending"
            
            # Extract name and timestamp
            name_match = re.search(r'<td class="TextSmall" align="left">(.*?)</td>', row)
            if not name_match:
                continue
                
            name_text = name_match.group(1).strip()
            
            # Split name and timestamp
            name_parts = name_text.split('<br>', 1)
            name = name_parts[0].strip()
            
            timestamp = ""
            if len(name_parts) > 1:
                # Extract timestamp from parentheses
                timestamp_match = re.search(r'\((.*?)\)', name_parts[1])
                if timestamp_match:
                    timestamp = timestamp_match.group(1).strip()
            
            # Skip if name is empty or just a status
            if not name or name in ["Ja!", "Nej!"]:
                continue
            
            # Extract guest count
            guests = 0
            guest_match = re.search(r'<td class="TextSmall" align="left" width="50">\s*\+(\d+)\s*</td>', row)
            if guest_match:
                guests = int(guest_match.group(1))
            
            # Extract comment
            comment = ""
            comment_match = re.search(r'<td class="TextSmall" >\s*(.*?)\s*</td>', row)
            if comment_match:
                comment = comment_match.group(1).strip()
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
        
        # Calculate total_attending (attendees + guests)
        result["total_attending"] = result["attendees"] + result["guests"]
        
        _LOGGER.info("Parsed activity info for '%s': %d attendees, %d rejects, %d no reply, %d guests", 
                    result["name"], result["attendees"], result["rejects"], 
                    result["no_reply"], result["guests"])
        
        return result

    """Public Functions"""

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
            
            # Parse the HTML directly
            result = self._parse_activity_info(html)
            
            return result
    
    async def reply_to_activity(self, event_id: str, user_id: str, reply_type: str, comment: str = "", guests: int = 0) -> bool:
        """Reply to an activity.
        
        Args:
            event_id: The ID of the event to reply to
            user_id: The ID of the user replying
            reply_type: Type of reply ('yes', 'no', or 'comment_only')
            comment: Optional comment to include with the reply
            guests: Number of guests to bring (default: 0)
            
        Returns:
            bool: True if reply was successful, False otherwise
        """
        url = f"{self.base_url}statAnswer.jsp?userId={user_id}&eventId={event_id}"
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://bokat.se",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Base data with optional comment
        data = {}
        if comment:
            # Ensure comment is properly encoded
            data["comment"] = comment.encode('utf-8').decode('utf-8')

        # Add specific fields based on reply type
        if reply_type == 'yes':
            data.update({
                "accept": "Tacka Ja",
                "currentStatus": "null"
            })
            if guests > 0:
                data["nrOfGuests"] = str(guests)
        elif reply_type == 'no':
            data.update({
                "decline": "Tacka Nej",
                "currentStatus": "null",
                "nrOfGuests": "0"
            })
        elif reply_type == 'comment_only':
            data["onlyComment"] = "Endast kommentar"
        else:
            _LOGGER.error("Invalid reply type: %s", reply_type)
            return False

        try:

            async with self._session.post(
                url=url,
                headers=headers,
                data=data,
                cookies=self._cookies,
                allow_redirects=True
            ) as response:
                response_text = await response.text()
                # Log response for debugging
                # _LOGGER.debug("Response status: %s, text: %s", response.status, response_text[:200])

                if response.status != 200:
                    _LOGGER.error("Failed to submit reply: %s", response.status)
                    return False
                    
                if '<b>Sparat.</b>' in response_text:
                    _LOGGER.info("Successfully replied to activity %s", event_id)
                    return True
                else:
                    _LOGGER.error("Reply submission failed for activity %s", event_id)
                    return False
                    
        except Exception as e:
            _LOGGER.error("Error submitting reply: %s", e)
            return False
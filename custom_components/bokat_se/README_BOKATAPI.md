# BokatAPI Module

A Python module for interacting with bokat.se without requiring login for most operations.

## Features

- `list_activities(username, password)`: Returns an array of activities with name and URL
- `get_activity(url)`: Returns an object with who signed up and an array with participants and their data scraped from that URL in real-time

## Usage

### As a Python Module

```python
import asyncio
from custom_components.bokat_se.bokatapi import list_activities, get_activity

async def main():
    # List all activities (requires login)
    activities = await list_activities("your_username", "your_password")
    print(f"Found {len(activities)} activities")
    
    if activities:
        # Get details for the first activity (no login required)
        activity_url = activities[0]["url"]
        activity_details = await get_activity(activity_url)
        print(f"Activity: {activity_details['name']}")
        print(f"Total participants: {activity_details['total_participants']}")
        print(f"Attending: {activity_details['attending_count']}")
        print(f"Not attending: {activity_details['not_attending_count']}")
        print(f"No response: {activity_details['no_response_count']}")

# Run the example
asyncio.run(main())
```

### From Command Line

The module can be run from the command line using the scripts in the `dev` folder:

```bash
# List all activities
python dev/bokatapi_cli.py list "your_username" "your_password"

# Get details for a specific activity
python dev/bokatapi_cli.py get "https://www.bokat.se/stat.jsp?eventId=12345&userId=67890"
```

## Development Tools

The `dev` folder contains scripts for testing and debugging:

- `bokatapi_cli.py`: Command-line interface for the BokatAPI module
- `example.py`: Example script demonstrating how to use the BokatAPI module
- `dev_deploy_simple.ps1`: PowerShell script for deploying the integration to Home Assistant

For more details, see the [Development README](../../dev/README.md).

## Notes

- Login is only required for listing activities
- Once you have an activity URL, you can access it without authentication
- The module uses BeautifulSoup for HTML parsing and aiohttp for HTTP requests
- All operations are asynchronous for better performance 
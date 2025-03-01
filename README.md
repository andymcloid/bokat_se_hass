# Bokat.se Integration for Home Assistant

A custom integration for Home Assistant that connects to Bokat.se and allows you to track your activities.

## Features

- Login to Bokat.se with your credentials
- View all activities
- Select which activity to track
- Display activity status in Home Assistant
- Regular updates of activity status
- View participant information including attendance status and comments
- Respond to events with attendance status, guest count, and comments
- Configurable update interval
- Custom Lovelace card for easy interaction

## Installation

### HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance
2. Add this repository as a custom repository in HACS:
   - Go to HACS → Integrations → ⋮ → Custom repositories
   - Add `https://github.com/andymcloid/bokat_se_hass` with category "Integration"
3. Install the "Bokat.se" integration from HACS
4. The Lovelace card will be automatically installed with the integration
5. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `custom_components/bokat_se` directory to your Home Assistant `custom_components` directory
3. Copy the `www/bokat-se-card.js` file to your Home Assistant `www` directory
4. Add the card as a resource in your Lovelace configuration:
   - Go to Configuration → Lovelace Dashboards → Resources
   - Add `/local/bokat-se-card.js` as a JavaScript module
5. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Bokat.se"
4. Enter your Bokat.se credentials (email and password)
5. Select which activity you want to track
6. Optionally, set a custom scan interval (5-180 minutes, default: 30)

## Usage

After configuration, a sensor will be created with the name based on your selected activity (e.g., `sensor.bokat_se_innebandy_sondag_kvall_tullinge`). This sensor will display the name of the selected activity and will have the following attributes:

- `activity_name`: The name of the selected activity
- `activity_status`: The status of the selected activity (number of participants, etc.)
- `activity_url`: The URL to the activity on Bokat.se
- `activities`: A list of all your activities
- `participants`: A list of all participants with their attendance status and comments
- `total_participants`: Total number of participants
- `attending_count`: Number of participants attending
- `not_attending_count`: Number of participants not attending
- `no_response_count`: Number of participants who haven't responded
- `answer_url`: URL to respond to the event

## Services

The integration provides the following services:

- `bokat_se.refresh`: Refresh the data from Bokat.se
- `bokat_se.select_activity`: Select a different activity to track
- `bokat_se.respond`: Respond to an event with attendance status, comment, and guests

### Service: bokat_se.refresh

Refresh the data from Bokat.se.

| Parameter | Description |
|-----------|-------------|
| entity_id | (Optional) The entity ID of the sensor to refresh. If not provided, all sensors will be refreshed. |

### Service: bokat_se.select_activity

Select a different activity to track.

| Parameter | Description |
|-----------|-------------|
| entity_id | (Required) The entity ID of the sensor. |
| activity_url | (Required) The URL of the activity to select. |

### Service: bokat_se.respond

Respond to an event with attendance status, comment, and guests.

| Parameter | Description |
|-----------|-------------|
| entity_id | (Required) The entity ID of the sensor. |
| attendance | (Required) The attendance status: "yes", "no", or "comment_only". |
| comment | (Optional) A comment to include with your response. |
| guests | (Optional) Number of guests you're bringing (only applicable when attendance is "yes"). Default: 0 |

## Lovelace Card

A custom Lovelace card is included to display the activity information and participant details. To use it:

1. Add the card to your dashboard:
   ```yaml
   type: 'custom:bokat-se-card'
   entity: sensor.bokat_se_your_activity_name
   title: 'Your Activity'
   ```

The card provides:
- Activity name and status
- Participant statistics (total, attending, not attending, no response)
- Detailed participant list with attendance status and comments
- Form to respond to the event with attendance status, guest count, and comments
- List of all activities with the ability to switch between them

## Automation Examples

### Notify when activity status changes

```yaml
automation:
  - alias: "Notify when activity status changes"
    trigger:
      - platform: state
        entity_id: sensor.bokat_se_innebandy_sondag_kvall_tullinge
    action:
      - service: notify.mobile_app
        data:
          title: "Bokat.se Activity Update"
          message: "{{ state_attr('sensor.bokat_se_innebandy_sondag_kvall_tullinge', 'activity_status') }}"
```

### Notify when someone responds to an event

```yaml
automation:
  - alias: "Notify when someone responds to an event"
    trigger:
      - platform: state
        entity_id: sensor.bokat_se_innebandy_sondag_kvall_tullinge
        attribute: attending_count
    action:
      - service: notify.mobile_app
        data:
          title: "Bokat.se Attendance Update"
          message: "{{ state_attr('sensor.bokat_se_innebandy_sondag_kvall_tullinge', 'attending_count') }} people are now attending"
```

### Respond to an event via automation

```yaml
automation:
  - alias: "Automatically respond to an event"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.bokat_se_innebandy_sondag_kvall_tullinge', 'answer_url') != '' }}"
    action:
      - service: bokat_se.respond
        data:
          entity_id: sensor.bokat_se_innebandy_sondag_kvall_tullinge
          attendance: "yes"
          comment: "I'll be there!"
          guests: 0
```

## Development

For development purposes, two scripts are included to help deploy changes to your Home Assistant instance without needing to push to GitHub:

- `dev_deploy.ps1` - PowerShell script for Windows users
- `dev_deploy.sh` - Bash script for Linux/macOS users

These scripts copy the integration files directly to your Home Assistant custom_components directory and the frontend card to the www directory.

### Development Configuration

To customize the deployment process, copy the `dev_config.json.template` file to `dev_config.json` and modify the settings:

```json
{
    "haConfigPath": "/config/custom_components/bokat_se",
    "sourceDir": "./custom_components/bokat_se",
    "restartHomeAssistant": false,
    "haUrl": "http://localhost:8123",
    "haToken": ""
}
```

Configuration options:
- `haConfigPath`: Path to your Home Assistant custom_components directory
- `sourceDir`: Path to the source directory of the integration
- `restartHomeAssistant`: Whether to restart Home Assistant after deployment (requires haToken)
- `haUrl`: URL to your Home Assistant instance (for restart functionality)
- `haToken`: Long-lived access token for Home Assistant (for restart functionality)

### Running the Deployment Scripts

#### Windows (PowerShell)
```powershell
.\dev_deploy.ps1
```

#### Linux/macOS (Bash)
```bash
chmod +x dev_deploy.sh
./dev_deploy.sh
```

Note: For the bash script, you need to have `jq` installed to parse the JSON configuration file. If `jq` is not installed, the script will use default values.

## License

MIT
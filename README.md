# Bokat.se Integration for Home Assistant

A custom integration for Home Assistant that connects to Bokat.se and allows you to track your activities.

## Features

- Login to Bokat.se with your credentials
- View all your activities
- Select which activity to track
- Display activity status in Home Assistant
- Regular updates of activity status

## Installation

### HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance
2. Add this repository as a custom repository in HACS:
   - Go to HACS → Integrations → ⋮ → Custom repositories
   - Add `https://github.com/yourusername/bokat_se` with category "Integration"
3. Install the "Bokat.se" integration from HACS
4. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `custom_components/bokat_se` directory to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Bokat.se"
4. Enter your Bokat.se credentials (email and password)
5. Select which activity you want to track

## Usage

After configuration, a sensor will be created with the name `sensor.bokat_se_youremail`. This sensor will display the name of the selected activity and will have the following attributes:

- `activity_name`: The name of the selected activity
- `activity_status`: The status of the selected activity (number of participants, etc.)
- `activity_url`: The URL to the activity on Bokat.se
- `activities`: A list of all your activities

## Services

The integration provides the following services:

- `bokat_se.refresh`: Refresh the data from Bokat.se
- `bokat_se.select_activity`: Select a different activity to track

## Automation Examples

### Notify when activity status changes

```yaml
automation:
  - alias: "Notify when activity status changes"
    trigger:
      - platform: state
        entity_id: sensor.bokat_se_youremail
    action:
      - service: notify.mobile_app
        data:
          title: "Bokat.se Activity Update"
          message: "{{ state_attr('sensor.bokat_se_youremail', 'activity_status') }}"
```

## License

MIT
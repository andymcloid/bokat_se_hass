"""Constants for the Bokat.se integration."""

DOMAIN = "bokat_se"
SCAN_INTERVAL = 1800  # 30 minutes in seconds
VERSION = "1.0.0"  # Used for cache busting in frontend resources

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACTIVITY_URL = "activity_url"
CONF_SCAN_INTERVAL = "scan_interval"

# Attributes
ATTR_ACTIVITY_NAME = "activity_name"
ATTR_ACTIVITY_STATUS = "activity_status"
ATTR_ACTIVITY_URL = "activity_url"
ATTR_ACTIVITIES = "activities"
ATTR_PARTICIPANTS = "participants"
ATTR_PARTICIPANT_NAME = "name"
ATTR_PARTICIPANT_STATUS = "status"
ATTR_PARTICIPANT_COMMENT = "comment"
ATTR_PARTICIPANT_TIMESTAMP = "timestamp"
ATTR_TOTAL_PARTICIPANTS = "total_participants"
ATTR_ATTENDING_COUNT = "attending_count"
ATTR_NOT_ATTENDING_COUNT = "not_attending_count"
ATTR_NO_RESPONSE_COUNT = "no_response_count"
ATTR_ANSWER_URL = "answer_url"

# Service names
SERVICE_REFRESH = "refresh"
SERVICE_SELECT_ACTIVITY = "select_activity"
SERVICE_RESPOND = "respond"

# Service parameters
ATTR_ENTITY_ID = "entity_id"
ATTR_ATTENDANCE = "attendance"
ATTR_COMMENT = "comment"
ATTR_GUESTS = "guests"

# Attendance status values
ATTENDANCE_YES = "yes"
ATTENDANCE_NO = "no"
ATTENDANCE_COMMENT_ONLY = "comment_only"

# Default values
DEFAULT_NAME = "Bokat.se"
DEFAULT_SCAN_INTERVAL = 30  # minutes

# Icons
ICON = "mdi:calendar-check" 
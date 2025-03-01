#!/bin/bash
# Bokat.se Development Deployment Script for Linux/macOS
# This script copies the custom component files to the Home Assistant config directory for testing

# Load configuration from dev_config.json if it exists
CONFIG_FILE="./dev_config.json"
if [ -f "$CONFIG_FILE" ]; then
    echo "Loading configuration from $CONFIG_FILE"
    if command -v jq >/dev/null 2>&1; then
        HA_CONFIG_PATH=$(jq -r '.haConfigPath // "/config/custom_components/bokat_se"' "$CONFIG_FILE")
        SOURCE_DIR=$(jq -r '.sourceDir // "./custom_components/bokat_se"' "$CONFIG_FILE")
        RESTART_HOME_ASSISTANT=$(jq -r '.restartHomeAssistant // false' "$CONFIG_FILE")
        HA_URL=$(jq -r '.haUrl // "http://localhost:8123"' "$CONFIG_FILE")
        HA_TOKEN=$(jq -r '.haToken // ""' "$CONFIG_FILE")
    else
        echo "Warning: jq is not installed. Using default values."
        HA_CONFIG_PATH="/config/custom_components/bokat_se"
        SOURCE_DIR="./custom_components/bokat_se"
        RESTART_HOME_ASSISTANT=false
        HA_URL="http://localhost:8123"
        HA_TOKEN=""
    fi
else
    echo "No configuration file found. Using default values."
    HA_CONFIG_PATH="/config/custom_components/bokat_se"
    SOURCE_DIR="./custom_components/bokat_se"
    RESTART_HOME_ASSISTANT=false
    HA_URL="http://localhost:8123"
    HA_TOKEN=""
fi

# Use environment variable for token if not in config
if [ -z "$HA_TOKEN" ]; then
    HA_TOKEN="$HA_TOKEN"
fi

# Display deployment configuration
echo "Deployment Configuration:"
echo "  Source Directory: $SOURCE_DIR"
echo "  Target Directory: $HA_CONFIG_PATH"
echo "  Restart Home Assistant: $RESTART_HOME_ASSISTANT"

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory does not exist: $SOURCE_DIR"
    exit 1
fi

# Check if Home Assistant config directory is accessible
HA_PARENT_DIR=$(dirname "$HA_CONFIG_PATH")
if [ ! -d "$HA_PARENT_DIR" ]; then
    echo "Creating parent directory: $HA_PARENT_DIR"
    mkdir -p "$HA_PARENT_DIR" || { echo "Error: Cannot create parent directory: $HA_PARENT_DIR"; exit 1; }
fi

if [ ! -d "$HA_CONFIG_PATH" ]; then
    echo "Creating target directory: $HA_CONFIG_PATH"
    mkdir -p "$HA_CONFIG_PATH" || { echo "Error: Cannot create target directory: $HA_CONFIG_PATH"; exit 1; }
fi

# Create translations directory if it doesn't exist
TRANSLATIONS_DIR="$HA_CONFIG_PATH/translations"
if [ ! -d "$TRANSLATIONS_DIR" ]; then
    echo "Creating translations directory: $TRANSLATIONS_DIR"
    mkdir -p "$TRANSLATIONS_DIR" || { echo "Error: Cannot create translations directory: $TRANSLATIONS_DIR"; exit 1; }
fi

# Create www directory in Home Assistant config if it doesn't exist
HA_WWW_DIR="$(dirname "$(dirname "$HA_CONFIG_PATH")")/www"
if [ ! -d "$HA_WWW_DIR" ]; then
    echo "Creating www directory: $HA_WWW_DIR"
    mkdir -p "$HA_WWW_DIR" || { echo "Error: Cannot create www directory: $HA_WWW_DIR"; exit 1; }
fi

# Copy all files from source directory to target directory
echo "Copying files from $SOURCE_DIR to $HA_CONFIG_PATH"
cp -R "$SOURCE_DIR"/* "$HA_CONFIG_PATH"/ || { echo "Error: Failed to copy files"; exit 1; }

# Copy translation files if they exist
SOURCE_TRANSLATIONS_DIR="$SOURCE_DIR/translations"
if [ -d "$SOURCE_TRANSLATIONS_DIR" ]; then
    echo "Copying translation files"
    cp -R "$SOURCE_TRANSLATIONS_DIR"/* "$TRANSLATIONS_DIR"/ || { echo "Error: Failed to copy translation files"; exit 1; }
fi

# Copy frontend card to www directory
SOURCE_WWW_DIR="$SOURCE_DIR/www"
if [ -d "$SOURCE_WWW_DIR" ]; then
    echo "Copying frontend card to www directory"
    cp -R "$SOURCE_WWW_DIR"/* "$HA_WWW_DIR"/ || { echo "Error: Failed to copy frontend card"; exit 1; }
fi

echo "Deployment completed successfully!"
echo "Remember to restart Home Assistant to apply changes."

# Restart Home Assistant if configured
if [ "$RESTART_HOME_ASSISTANT" = true ]; then
    echo "Restarting Home Assistant..."
    if [ -z "$HA_TOKEN" ]; then
        echo "Error: No Home Assistant token found. Set the HA_TOKEN environment variable or add haToken to dev_config.json."
    else
        curl -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" "$HA_URL/api/services/homeassistant/restart"
        if [ $? -eq 0 ]; then
            echo "Restart command sent to Home Assistant."
        else
            echo "Error restarting Home Assistant."
        fi
    fi
fi 
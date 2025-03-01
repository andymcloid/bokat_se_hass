#!/bin/bash
# Bokat.se Development Setup Script for Linux/macOS
# This script helps set up the development environment for the Bokat.se integration

echo -e "\033[1;36mSetting up development environment for Bokat.se integration...\033[0m"

# Check if dev_config.json already exists
if [ -f "./dev_config.json" ]; then
    echo -e "\033[1;33mdev_config.json already exists. Skipping creation.\033[0m"
else
    # Copy template to dev_config.json
    if [ -f "./dev_config.json.template" ]; then
        echo -e "\033[1;32mCreating dev_config.json from template...\033[0m"
        cp "./dev_config.json.template" "./dev_config.json"
        echo -e "\033[1;32mCreated dev_config.json. Please edit this file with your specific configuration.\033[0m"
    else
        echo -e "\033[1;31mError: dev_config.json.template not found.\033[0m"
        echo -e "\033[1;33mCreating a basic dev_config.json file...\033[0m"
        
        # Create a basic config file
        cat > "./dev_config.json" << EOF
{
    "haConfigPath": "/path/to/homeassistant/config/custom_components/bokat_se",
    "sourceDir": "./custom_components/bokat_se",
    "restartHomeAssistant": false,
    "haUrl": "http://localhost:8123",
    "haToken": ""
}
EOF
        echo -e "\033[1;32mCreated basic dev_config.json. Please edit this file with your specific configuration.\033[0m"
    fi
fi

# Check if the source directory exists
if [ ! -d "./custom_components/bokat_se" ]; then
    echo -e "\033[1;32mCreating directory structure...\033[0m"
    mkdir -p "./custom_components/bokat_se/translations"
    mkdir -p "./custom_components/bokat_se/www"
    echo -e "\033[1;32mDirectory structure created.\033[0m"
else
    echo -e "\033[1;33mDirectory structure already exists.\033[0m"
fi

# Make the deployment script executable
if [ -f "./dev_deploy.sh" ]; then
    chmod +x ./dev_deploy.sh
    echo -e "\033[1;32mMade dev_deploy.sh executable.\033[0m"
fi

echo -e "\n\033[1;36mDevelopment environment setup complete!\033[0m"
echo -e "\033[1;37mNext steps:\033[0m"
echo -e "\033[1;37m1. Edit dev_config.json with your specific configuration\033[0m"
echo -e "\033[1;37m2. Run ./dev_deploy.sh to deploy your changes to Home Assistant\033[0m"
echo -e "\033[1;37m3. Start developing!\033[0m" 
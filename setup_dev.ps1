# Bokat.se Development Setup Script for Windows
# This script helps set up the development environment for the Bokat.se integration

Write-Host "Setting up development environment for Bokat.se integration..." -ForegroundColor Cyan

# Check if dev_config.json already exists
if (Test-Path -Path "./dev_config.json") {
    Write-Host "dev_config.json already exists. Skipping creation." -ForegroundColor Yellow
} else {
    # Copy template to dev_config.json
    if (Test-Path -Path "./dev_config.json.template") {
        Write-Host "Creating dev_config.json from template..." -ForegroundColor Green
        Copy-Item -Path "./dev_config.json.template" -Destination "./dev_config.json"
        Write-Host "Created dev_config.json. Please edit this file with your specific configuration." -ForegroundColor Green
    } else {
        Write-Host "Error: dev_config.json.template not found." -ForegroundColor Red
        Write-Host "Creating a basic dev_config.json file..." -ForegroundColor Yellow
        
        # Create a basic config file
        $config = @{
            haConfigPath = "C:\path\to\homeassistant\config\custom_components\bokat_se"
            sourceDir = ".\custom_components\bokat_se"
            restartHomeAssistant = $false
            haUrl = "http://localhost:8123"
            haToken = ""
        }
        
        $config | ConvertTo-Json | Out-File -FilePath "./dev_config.json"
        Write-Host "Created basic dev_config.json. Please edit this file with your specific configuration." -ForegroundColor Green
    }
}

# Check if the source directory exists
if (-Not (Test-Path -Path "./custom_components/bokat_se")) {
    Write-Host "Creating directory structure..." -ForegroundColor Green
    New-Item -Path "./custom_components/bokat_se" -ItemType Directory -Force | Out-Null
    New-Item -Path "./custom_components/bokat_se/translations" -ItemType Directory -Force | Out-Null
    New-Item -Path "./custom_components/bokat_se/www" -ItemType Directory -Force | Out-Null
    Write-Host "Directory structure created." -ForegroundColor Green
} else {
    Write-Host "Directory structure already exists." -ForegroundColor Yellow
}

Write-Host "`nDevelopment environment setup complete!" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor White
Write-Host "1. Edit dev_config.json with your specific configuration" -ForegroundColor White
Write-Host "2. Run .\dev_deploy.ps1 to deploy your changes to Home Assistant" -ForegroundColor White
Write-Host "3. Start developing!" -ForegroundColor White 
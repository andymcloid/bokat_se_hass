# Bokat.se Development Deployment Script for Windows
# This script copies the custom component files to the Home Assistant config directory for testing

# Load configuration from dev_config.json if it exists
$configFile = ".\dev_config.json"
$config = $null

try {
    if (Test-Path $configFile) {
        $config = Get-Content $configFile -Raw | ConvertFrom-Json
        Write-Host "Loaded configuration from $configFile"
    }
} catch {
    Write-Host "Error loading configuration from $configFile. Using default values."
    $config = $null
}

# Set default values if config is not loaded
$haConfigPath = if ($config -and $config.haConfigPath) { $config.haConfigPath } else { "\\homeassistant\config\custom_components\bokat_se" }
$sourceDir = if ($config -and $config.sourceDir) { $config.sourceDir } else { ".\custom_components\bokat_se" }
$restartHomeAssistant = if ($config -and $config.restartHomeAssistant -ne $null) { $config.restartHomeAssistant } else { $false }

# Display deployment configuration
Write-Host "Deployment Configuration:"
Write-Host "  Source Directory: $sourceDir"
Write-Host "  Target Directory: $haConfigPath"
Write-Host "  Restart Home Assistant: $restartHomeAssistant"

# Check if source directory exists
if (-not (Test-Path $sourceDir)) {
    Write-Host "Error: Source directory does not exist: $sourceDir" -ForegroundColor Red
    exit 1
}

# Check if Home Assistant config directory is accessible
try {
    if (-not (Test-Path (Split-Path $haConfigPath -Parent))) {
        Write-Host "Creating parent directory: $(Split-Path $haConfigPath -Parent)"
        New-Item -Path (Split-Path $haConfigPath -Parent) -ItemType Directory -Force | Out-Null
    }
    
    if (-not (Test-Path $haConfigPath)) {
        Write-Host "Creating target directory: $haConfigPath"
        New-Item -Path $haConfigPath -ItemType Directory -Force | Out-Null
    }
} catch {
    Write-Host "Error: Cannot access Home Assistant config directory: $haConfigPath" -ForegroundColor Red
    Write-Host "  $_"
    exit 1
}

# Create translations directory if it doesn't exist
$translationsDir = Join-Path $haConfigPath "translations"
if (-not (Test-Path $translationsDir)) {
    Write-Host "Creating translations directory: $translationsDir"
    New-Item -Path $translationsDir -ItemType Directory -Force | Out-Null
}

# Create www directory in Home Assistant config if it doesn't exist
$haWwwDir = Join-Path (Split-Path $haConfigPath -Parent) "..\www"
if (-not (Test-Path $haWwwDir)) {
    Write-Host "Creating www directory: $haWwwDir"
    New-Item -Path $haWwwDir -ItemType Directory -Force | Out-Null
}

# Copy all files from source directory to target directory
Write-Host "Copying files from $sourceDir to $haConfigPath"
Copy-Item -Path "$sourceDir\*" -Destination $haConfigPath -Recurse -Force

# Copy translation files if they exist
$sourceTranslationsDir = Join-Path $sourceDir "translations"
if (Test-Path $sourceTranslationsDir) {
    Write-Host "Copying translation files"
    Copy-Item -Path "$sourceTranslationsDir\*" -Destination $translationsDir -Force
}

# Copy frontend card to www directory
$sourceWwwDir = Join-Path $sourceDir "www"
if (Test-Path $sourceWwwDir) {
    Write-Host "Copying frontend card to www directory"
    Copy-Item -Path "$sourceWwwDir\*" -Destination $haWwwDir -Force
}

Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host "Remember to restart Home Assistant to apply changes."

# Restart Home Assistant if configured
if ($restartHomeAssistant) {
    Write-Host "Restarting Home Assistant..."
    try {
        $haUrl = if ($config -and $config.haUrl) { $config.haUrl } else { "http://homeassistant:8123" }
        $haToken = if ($config -and $config.haToken) { $config.haToken } else { $env:HA_TOKEN }
        
        if (-not $haToken) {
            Write-Host "Error: No Home Assistant token found. Set the HA_TOKEN environment variable or add haToken to dev_config.json." -ForegroundColor Red
        } else {
            $headers = @{
                "Authorization" = "Bearer $haToken"
                "Content-Type" = "application/json"
            }
            
            Invoke-RestMethod -Uri "$haUrl/api/services/homeassistant/restart" -Method Post -Headers $headers
            Write-Host "Restart command sent to Home Assistant." -ForegroundColor Green
        }
    } catch {
        Write-Host "Error restarting Home Assistant: $_" -ForegroundColor Red
    }
} 
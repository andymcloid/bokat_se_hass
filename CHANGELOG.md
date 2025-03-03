# Changelog

## 2.1.0 (2023-03-04)

### Changed
- Removed unnecessary debug logging throughout the codebase
- Improved code efficiency by removing unused imports
- Cleaner frontend code with removal of console.log statements

### Fixed
- Fixed missing timedelta import causing setup errors

### Developer
- Code cleanup and optimization
- Removed unused imports while keeping essential dependencies
- Followed project coding style guidelines for better maintainability

## 2.0.0 (2025-03-03)

### Added
- Improved reply functionality with proper API endpoints
- Added support for comment-only replies
- Added proper guest count handling for accept replies
- Added debug logging for API operations
- Added visual editor for card configuration
- Added filtering for Bokat.se sensors in the editor

### Changed
- Updated API endpoints to use correct URLs
- Improved error handling and logging
- Updated service descriptions to be more accurate
- Improved card styling and layout
- Better participant status display

### Fixed
- Fixed reply endpoint using incorrect URL
- Fixed guest count not being sent correctly
- Fixed compatibility issues with Home Assistant
- Fixed incorrect parameter names in API calls

### Developer
- Refactored BokatAPI class for better maintainability
- Added proper type hints and docstrings
- Improved error handling and logging
- Added development tools and documentation
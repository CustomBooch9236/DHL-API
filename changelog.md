# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-04-16

### Added
- Initial release of the DHL Tracking Application with GUI.
- AWB tracking via DHL API.
- Search functionality with multiple AWBs.
- Sortable Treeview displaying AWB, Origin, Destination, Status, and Timestamp.
- Filter panel with dropdowns for AWB, Origin, and Status.
- Export functionality supporting CSV and Excel formats.
- Column selection in export settings.
- Settings and About tabs with project details.
- Basic note-taking section with support for bold, italics, and underline.

### Fixed
- Ensured compatibility with older versions of OpenSSL.

### Known Issues
- UI resizing behaviour for all elements not fully responsive.
- No persistent saving for notes; lost on app close.
- Rate error, Error Code 429
- Random value errors

## [1.1.0] - 2025-04-17

### Added
- Caching improvement: The app now checks if the tracking number exists in the cache before querying the DHL API to avoid redundant requests.
- Auto-refresh feature: Automatic periodic updates of AWB status, based on a user-defined interval in the Settings tab.

### Fixed
- User input handling: Added input validation to ensure that the auto-refresh interval is a positive integer, avoiding errors and ensuring stability.
- User input handling: Added input validation to ensure that the auto-refresh interval is a positive integer, avoiding errors and ensuring stability.

### Known Issues
- UI resizing behaviour for all elements not fully responsive.
- Notes section does not persist across app restarts.
- Filters currently not functional

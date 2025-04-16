# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-04-16

### Added
- Initial release of the DHL Tracking Application with GUI.
- Logo integration with Cummins and DHL branding.
- AWB tracking via DHL API.
- Search functionality with multiple AWBs.
- Sortable Treeview displaying AWB, Origin, Destination, Status, and Timestamp.
- Filter panel with dropdowns for AWB, Origin, and Status.
- Export functionality supporting CSV and Excel formats.
- Column selection in export settings.
- Settings and About tabs with project details.
- Basic note-taking section with support for bold, italics, and underline.
- Executable version compiled with custom icon.
- Project assets including README, LICENSE, and `.exe`.

### Fixed
- Handled API errors and rate limit responses gracefully.
- Ensured compatibility with older versions of OpenSSL.

### Known Issues
- UI resizing behaviour for all elements not fully responsive.
- No persistent saving for notes; lost on app close.

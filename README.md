# DHL-API
This DHL Tracking App, built with Python's Tkinter and PyQt5, allows users to track shipments by AWB numbers, display details like origin, destination, status, and timestamp, and apply filters. It supports exporting data to CSV or Excel, includes a notes section with rich-text editing, and features a user login system with personalized API keys.

## Features

- Input and search for multiple AWB tracking numbers
- View shipment details including origin, destination, status, and timestamp
- Filter data by AWB, Origin, and Status
- Export filtered data to CSV or Excel
- Rich-text note-taking area with bold, italics, and underline support
- Clean, tabbed UI with dedicated sections for Tracking, Cache, Settings, and About
- User login system with support for user-specific API keys
- Real-time current time display in the app
- Cache management for faster tracking data retrieval
- Auto-refresh feature for periodic status updates
- Persistent note-taking that saves across app restarts

## Libraries Used

- `tkinter`: GUI framework for building the interface
- `PyQt5`: For advanced UI features and tab management
- `ttk`: Themed widgets for enhanced appearance
- `PIL` (Pillow): For image processing and logo display
- `requests`: To handle API calls to DHL’s shipment tracking service
- `ssl` & `urllib3`: To manage secure HTTP requests and suppress warnings
- `json`: For parsing API responses
- `csv`: For exporting data in CSV format
- `openpyxl`: For creating and saving Excel (.xlsx) files
- `datetime`: To manage and format timestamps

## Future Updates
- Enhanced user profile management features
- Increased API calls
- PoD functionality

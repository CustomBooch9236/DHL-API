# DHL-API
This DHL Tracking App, built with Python's Tkinter, allows users to track shipments by AWB numbers, display details like origin, destination, status, and timestamp, and apply filters. It supports exporting data to CSV or Excel, and includes a notes section with basic text editing.

## Features

- Input and search for multiple AWB tracking numbers
- View shipment details including origin, destination, status, and timestamp
- Filter data by AWB, Origin, and Status
- Export filtered data to CSV or Excel
- Rich-text note-taking area with bold, italics, and underline support
- Clean, tabbed UI with dedicated sections for Tracking, Settings, and About

## Libraries Used

- `tkinter`: GUI framework for building the interface
- `ttk`: Themed widgets for enhanced appearance
- `PIL` (Pillow): For image processing and logo display
- `requests`: To handle API calls to DHL’s shipment tracking service
- `ssl` & `urllib3`: To manage secure HTTP requests and suppress warnings
- `json`: For parsing API responses
- `csv`: For exporting data in CSV format
- `openpyxl`: For creating and saving Excel (.xlsx) files
- `datetime`: To manage and format timestamps

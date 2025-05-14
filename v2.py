import sys
import json
import csv
import os
from datetime import datetime
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QComboBox, QTextEdit, QMessageBox, QDialog,
                             QFormLayout, QCheckBox, QFileDialog, QGroupBox, QProgressBar)
from PyQt5.QtGui import QFont, QIcon, QTextCharFormat, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QThread
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants
APP_NAME = "DHL Tracker"
APP_VERSION = "2.0"
SETTINGS_FILE = "settings.json"
CACHE_FILE = "cache.json"

# Base API endpoints for different users
API_ENDPOINTS = {
    "Cummins UK": "https://api-eu.dhl.com/track/shipments",
    "Cummins BE": "https://api-eu.dhl.com/track/shipments",
    "Cummins DE": "https://api-eu.dhl.com/track/shipments",
    "Cummins NL": "https://api-eu.dhl.com/track/shipments"
}

class ApiWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, api_client, awb_list):
        super().__init__()
        self.api_client = api_client
        self.awb_list = awb_list
        
    def run(self):
        results = []
        total = len(self.awb_list)
        
        for i, awb in enumerate(self.awb_list):
            try:
                self.progress.emit(int((i / total) * 100))
                result = self.api_client.track_shipment(awb)
                if result:
                    results.append(result)
            except Exception as e:
                self.error.emit(f"Error tracking AWB {awb}: {str(e)}")
                
        self.progress.emit(100)
        self.finished.emit(results)

class TrackingApiClient:
    def __init__(self, user_label, api_key):
        self.user_label = user_label
        self.api_key = api_key
        self.base_url = "https://api-eu.dhl.com/track/shipments"

    def track_shipment(self, awb):
        if not awb:
            return None

        headers = {
            "DHL-API-Key": self.api_key,
            "Accept": "application/json"
        }
        params = {
            "trackingNumber": awb,
            "service": "express"
        }

        response = requests.get(
            self.base_url,
            headers=headers,
            params=params,
            timeout=30,
            verify=False  # Only for dev environments
        )
        data = response.json()

        if not data.get("shipments"):
            return {
                'awb': awb,
                'origin': "UNKNOWN",
                'destination': "UNKNOWN",
                'status': "Unavailable",
                'timestamp': "N/A",
                'delivered_on': "N/A"
            }

        shipment = data["shipments"][0]

        # Last event = most recent checkpoint
        events = shipment.get("events", [])
        last_event = events[0] if events else {}
        last_status = last_event.get("statusCode", "N/A").capitalize()
        last_timestamp = last_event.get("timestamp", "")

        # Find the delivery timestamp if it exists
        delivered_on = "N/A"
        for event in events:
            if event.get("statusCode", "").lower() == "delivered":
                delivered_on = event.get("timestamp", "N/A")
                break

        try:
            last_timestamp_fmt = datetime.fromisoformat(last_timestamp).strftime('%Y-%m-%d %H:%M:%S') if last_timestamp else "N/A"
        except ValueError:
            last_timestamp_fmt = last_timestamp or "N/A"

        try:
            delivered_fmt = datetime.fromisoformat(delivered_on).strftime('%Y-%m-%d %H:%M:%S') if delivered_on != "N/A" else "N/A"
        except ValueError:
            delivered_fmt = delivered_on

        return {
            'awb': awb,
            'origin': shipment.get("origin", {}).get("address", {}).get("addressLocality", "UNKNOWN"),
            'destination': shipment.get("destination", {}).get("address", {}).get("addressLocality", "UNKNOWN"),
            'status': last_status,
            'timestamp': last_timestamp_fmt,
            'delivered_on': delivered_fmt
        }

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setMinimumWidth(300)
        
        # User credentials and API keys, PLEASE ADD YOU OWN
        self.users = {
            "Cummins UK": "",
            "Cummins BE": "",
            "Cummins DE": "",
            "Cummins NL": ""
        }
        
        self.api_keys = {
            "Cummins UK": "",
            "Cummins DE": "",
            "Cummins NL": "",  
            "Cummins BE": ""
        }
        
        # Setup UI
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        self.username_input = QComboBox()
        self.username_input.addItems(list(self.users.keys()))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Password:", self.password_input)
        
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.try_login)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.login_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def try_login(self):
        username = self.username_input.currentText()
        password = self.password_input.text()
        
        if username in self.users and self.users[username] == password:
            self.current_user = username
            self.current_api = self.api_keys[username]
            self.accept()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password")

class RichTextEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        
    def format_text(self, format_type):
        format = QTextCharFormat()
        
        if format_type == "bold":
            format.setFontWeight(QFont.Bold if self.textCursor().charFormat().fontWeight() != QFont.Bold 
                              else QFont.Normal)
        elif format_type == "italic":
            format.setFontItalic(not self.textCursor().charFormat().fontItalic())
        elif format_type == "underline":
            format.setFontUnderline(not self.textCursor().charFormat().fontUnderline())
            
        self.mergeCurrentCharFormat(format)

class AWBTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(800, 600)
        
        # Show login dialog
        login_dialog = LoginDialog(self)
        if login_dialog.exec_() == QDialog.Accepted:
            self.current_user = login_dialog.current_user
            self.current_api = login_dialog.current_api
            
            # Initialize API client
            self.api_client = TrackingApiClient(self.current_user, self.current_api)
        else:
            sys.exit()
        
        # Load cache data
        self.cache_data = self.load_cache()
        
        self.init_ui()
    
    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout()
        
        # Status bar for showing current user
        self.statusBar().showMessage(f"Logged in as: {self.current_user}")
        
        # Create tabs
        self.tabs = QTabWidget()
        self.tracking_tab = QWidget()
        self.cache_tab = QWidget()
        self.settings_tab = QWidget()
        self.about_tab = QWidget()
        
        # Set up each tab
        self.setup_tracking_tab()
        self.setup_cache_tab()
        self.setup_settings_tab()
        self.setup_about_tab()
        
        # Add tabs to widget
        self.tabs.addTab(self.tracking_tab, "Tracking")
        self.tabs.addTab(self.cache_tab, "Cache")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.about_tab, "About")
        
        main_layout.addWidget(self.tabs)
        self.central_widget.setLayout(main_layout)
    
    def setup_tracking_tab(self):
        layout = QVBoxLayout()
        
        # Search section
        search_layout = QHBoxLayout()
        self.awb_input = QLineEdit()
        self.awb_input.setPlaceholderText("Enter AWB number(s) - separate multiple with commas")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_awb)
        
        search_layout.addWidget(QLabel("AWB:"))
        search_layout.addWidget(self.awb_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Results section with filters
        filter_layout = QHBoxLayout()
        
        self.filter_awb = QLineEdit()
        self.filter_awb.setPlaceholderText("Filter AWB")
        self.filter_awb.textChanged.connect(self.apply_filters)
        
        self.filter_origin = QComboBox()
        self.filter_origin.addItem("All Origins")
        self.filter_origin.currentTextChanged.connect(self.apply_filters)
        
        self.filter_status = QComboBox()
        self.filter_status.addItem("All Statuses")
        self.filter_status.currentTextChanged.connect(self.apply_filters)
        
        filter_layout.addWidget(QLabel("Filter:"))
        filter_layout.addWidget(self.filter_awb)
        filter_layout.addWidget(self.filter_origin)
        filter_layout.addWidget(self.filter_status)
        
        export_button = QPushButton("Export Data")
        export_button.clicked.connect(self.export_data)
        filter_layout.addWidget(export_button)
        
        layout.addLayout(filter_layout)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["AWB", "Origin", "Destination", "Status", "Delivered On"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)
        
        # Note taking area
        notes_layout = QVBoxLayout()
        format_layout = QHBoxLayout()
        
        format_buttons = []
        for btn_text, format_type in [("B", "bold"), ("I", "italic"), ("U", "underline")]:
            btn = QPushButton(btn_text)
            btn.setMaximumWidth(30)
            
            if format_type == "bold":
                btn.setFont(QFont("Arial", 10, QFont.Bold))
            elif format_type == "italic":
                btn.setFont(QFont("Arial", 10, QFont.StyleItalic))
                
            btn.clicked.connect(lambda _, fmt=format_type: self.note_editor.format_text(fmt))
            format_buttons.append(btn)
        
        format_layout.addWidget(QLabel("Notes:"))
        for btn in format_buttons:
            format_layout.addWidget(btn)
        format_layout.addStretch()
        
        self.note_editor = RichTextEditor()
        
        notes_layout.addLayout(format_layout)
        notes_layout.addWidget(self.note_editor)
        
        layout.addLayout(notes_layout)
        self.tracking_tab.setLayout(layout)
    
    def setup_cache_tab(self):
        layout = QVBoxLayout()
        
        # Cache information
        info_layout = QHBoxLayout()
        self.cache_count_label = QLabel(str(len(self.cache_data)))
        
        info_layout.addWidget(QLabel("Cached Shipments:"))
        info_layout.addWidget(self.cache_count_label)
        info_layout.addStretch()
        
        clear_cache_button = QPushButton("Clear Cache")
        clear_cache_button.clicked.connect(self.clear_cache)
        info_layout.addWidget(clear_cache_button)
        
        layout.addLayout(info_layout)
        
        # Cache table
        self.cache_table = QTableWidget()
        self.cache_table.setColumnCount(6)
        self.cache_table.setHorizontalHeaderLabels(["AWB", "Origin", "Destination", "Status", "Last Update", "Delivered On"])
        self.cache_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.cache_table)
        
        # Filter options (reused from tracking tab)
        filter_layout = QHBoxLayout()
        
        self.cache_filter_awb = QLineEdit()
        self.cache_filter_awb.setPlaceholderText("Filter AWB")
        self.cache_filter_awb.textChanged.connect(self.apply_cache_filters)
        
        self.cache_filter_origin = QComboBox()
        self.cache_filter_origin.addItem("All Origins")
        self.cache_filter_origin.currentTextChanged.connect(self.apply_cache_filters)
        
        self.cache_filter_status = QComboBox()
        self.cache_filter_status.addItem("All Statuses")
        self.cache_filter_status.currentTextChanged.connect(self.apply_cache_filters)
        
        filter_layout.addWidget(QLabel("Filter:"))
        filter_layout.addWidget(self.cache_filter_awb)
        filter_layout.addWidget(self.cache_filter_origin)
        filter_layout.addWidget(self.cache_filter_status)
        
        export_cache_button = QPushButton("Export Cache Data")
        export_cache_button.clicked.connect(self.export_cache_data)
        filter_layout.addWidget(export_cache_button)
        
        layout.addLayout(filter_layout)
        self.cache_tab.setLayout(layout)
        
        # Populate cache table
        self.update_cache_display()
    
    def setup_settings_tab(self):
        layout = QVBoxLayout()
        
        # User information section
        user_group = QGroupBox("User Information")
        user_layout = QFormLayout()
        
        self.current_user_label = QLabel(self.current_user)
        
        # API key section with masked display
        api_layout = QHBoxLayout()
        self.api_key_label = QLineEdit(self.current_api)
        self.api_key_label.setEchoMode(QLineEdit.Password)
        self.api_key_label.setReadOnly(True)
        
        self.toggle_api_visibility = QPushButton("Show")
        self.toggle_api_visibility.clicked.connect(self.toggle_api_key_visibility)
        
        api_layout.addWidget(self.api_key_label)
        api_layout.addWidget(self.toggle_api_visibility)
        
        # Endpoint display
        self.endpoint_label = QLineEdit(API_ENDPOINTS.get(self.current_user, "Unknown"))
        self.endpoint_label.setReadOnly(True)
        
        user_layout.addRow("Current User:", self.current_user_label)
        user_layout.addRow("API Key:", api_layout)
        user_layout.addRow("API Endpoint:", self.endpoint_label)
        
        user_group.setLayout(user_layout)
        layout.addWidget(user_group)
        
        # Application settings
        app_settings_group = QGroupBox("Application Settings")
        settings_layout = QFormLayout()
        
        self.cache_enabled = QCheckBox()
        self.cache_enabled.setChecked(True)
        
        self.cache_days = QComboBox()
        for days in [1, 3, 7, 14, 30]:
            self.cache_days.addItem(f"{days} days")
        self.cache_days.setCurrentIndex(2)  # Default to 7 days
        
        self.api_timeout = QComboBox()
        for timeout in [10, 20, 30, 60]:
            self.api_timeout.addItem(f"{timeout} seconds")
        self.api_timeout.setCurrentIndex(2)  # Default to 30 seconds
        
        self.retry_count = QComboBox()
        for count in [0, 1, 2, 3]:
            self.retry_count.addItem(f"{count} retries")
        self.retry_count.setCurrentIndex(1)  # Default to 1 retry
        
        settings_layout.addRow("Enable Cache:", self.cache_enabled)
        settings_layout.addRow("Cache Duration:", self.cache_days)
        settings_layout.addRow("API Timeout:", self.api_timeout)
        settings_layout.addRow("Connection Retries:", self.retry_count)
        
        app_settings_group.setLayout(settings_layout)
        layout.addWidget(app_settings_group)
        
        # Action buttons
        test_api_button = QPushButton("Test API Connection")
        test_api_button.clicked.connect(self.test_api_connection)
        
        save_settings_button = QPushButton("Save Settings")
        save_settings_button.clicked.connect(self.save_settings)
        
        layout.addWidget(test_api_button)
        layout.addWidget(save_settings_button)
        layout.addStretch()
        
        self.settings_tab.setLayout(layout)
    
    def setup_about_tab(self):
        layout = QVBoxLayout()
        
        about_text = f"""
        <h1>{APP_NAME} v{APP_VERSION}</h1>
        <p>An application for tracking air waybill (AWB) shipments.</p>
        <p><b>Features:</b></p>
        <ul>
            <li>Search for multiple AWB tracking numbers</li>
            <li>View shipment details including origin, destination, status, and timestamp</li>
            <li>Filter data by AWB, Origin, and Status</li>
            <li>Persistent caching tracking information to reduce API calls</li>
            <li>Export filtered data to CSV</li>
            <li>Rich-text note-taking with formatting support</li>
        </ul>
        <p>&copy; 2025 All rights reserved.</p>
        """
        
        about_label = QLabel(about_text)
        about_label.setTextFormat(Qt.RichText)
        about_label.setWordWrap(True)
        about_label.setAlignment(Qt.AlignTop)
        
        layout.addWidget(about_label)
        layout.addStretch()
        
        self.about_tab.setLayout(layout)
    
    def toggle_api_key_visibility(self):
        if self.api_key_label.echoMode() == QLineEdit.Password:
            self.api_key_label.setEchoMode(QLineEdit.Normal)
            self.toggle_api_visibility.setText("Hide")
        else:
            self.api_key_label.setEchoMode(QLineEdit.Password)
            self.toggle_api_visibility.setText("Show")
    
    def test_api_connection(self):
        try:
            response = requests.get(
                f"{API_ENDPOINTS.get(self.current_user, '')}status",
                headers={"Authorization": f"Bearer {self.current_api}"},
                timeout=10,
                verify=False  
            )

            if response.status_code == 200:
                QMessageBox.information(
                    self, "API Test Successful",
                    f"Successfully connected to the {self.current_user} API."
                )
            else:
                QMessageBox.warning(
                    self, "API Test Failed",
                    f"Failed to connect: {response.status_code} - {response.text}"
                )
        except Exception as e:
            QMessageBox.critical(
                self, "API Connection Error",
                f"Error connecting to API: {str(e)}"
            )

    def search_awb(self):
        awb_input = self.awb_input.text().strip()
        if not awb_input:
            QMessageBox.warning(self, "Input Error", "Please enter at least one AWB number.")
            return
        
        # Split by commas to handle multiple AWBs
        awb_list = [awb.strip() for awb in awb_input.split(',') if awb.strip()]
        
        # Clear current results
        self.results_table.setRowCount(0)
        
        # First check cache for the AWBs if cache is enabled
        found_in_cache = []
        remaining_awbs = awb_list.copy()
        
        if self.cache_enabled.isChecked():
            for awb in awb_list:
                for entry in self.cache_data:
                    if entry['awb'] == awb:
                        found_in_cache.append(entry)
                        if awb in remaining_awbs:
                            remaining_awbs.remove(awb)
                        break
        
        # Show progress bar for API calls
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(bool(remaining_awbs))
        
        # If there are AWBs not in cache, make API calls in a separate thread
        if remaining_awbs:
            self.api_worker = ApiWorker(self.api_client, remaining_awbs)
            self.api_worker.progress.connect(self.update_progress)
            self.api_worker.finished.connect(lambda results: self.process_api_results(results, found_in_cache))
            self.api_worker.error.connect(self.show_api_error)
            self.api_worker.start()
        else:
            # If all AWBs were found in cache, just display those results
            self.display_results(found_in_cache)
            self.update_filter_options(found_in_cache)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def show_api_error(self, error_message):
        self.statusBar().showMessage(error_message, 5000)  # Show for 5 seconds
    
    def process_api_results(self, api_results, cache_results):
        self.progress_bar.setVisible(False)
        
        # Add new results to cache if cache is enabled
        if self.cache_enabled.isChecked() and api_results:
            self.cache_data.extend(api_results)
            self.save_cache()
        
        # Combine results from cache and API
        all_results = cache_results + api_results
        
        # Display combined results
        self.display_results(all_results)
        
        # Update available filter options
        self.update_filter_options(all_results)
        
        # Show message about results
        if all_results:
            self.statusBar().showMessage(f"Found {len(all_results)} shipments", 3000)
        else:
            self.statusBar().showMessage("No shipments found", 3000)
    
    def display_results(self, results):
        self.results_table.setRowCount(len(results))
        
        # Status color mapping
        color_map = {
            'delivered': QColor(200, 255, 200),  # Light green
            'transit': QColor(230, 230, 255),    # Light blue
            'delayed': QColor(255, 200, 200),    # Light red
            'exception': QColor(255, 200, 200)   # Light red
        }
        
        for row, data in enumerate(results):
            # Set row data
            for col, value in enumerate([
                data['awb'],
                data['origin'],
                data['destination'],
                data['status'],
                data.get('delivered_on', 'N/A')
            ]):

                item = QTableWidgetItem(value)
                self.results_table.setItem(row, col, item)
            
            # Apply color coding based on status
            status = data['status'].lower()
            for status_key, color in color_map.items():
                if status_key in status:
                    for col in range(5):
                        self.results_table.item(row, col).setBackground(color)
                    break
    
    def update_filter_options(self, results):
        # Save current selections
        current_origin = self.filter_origin.currentText()
        current_status = self.filter_status.currentText()
        
        # Clear and repopulate filter options
        self.filter_origin.clear()
        self.filter_status.clear()
        
        self.filter_origin.addItem("All Origins")
        self.filter_status.addItem("All Statuses")
        
        # Collect unique values
        origins = set(data['origin'] for data in results)
        statuses = set(data['status'] for data in results)
        
        # Add to dropdowns
        for origin in sorted(origins):
            self.filter_origin.addItem(origin)
        
        for status in sorted(statuses):
            self.filter_status.addItem(status)
        
        # Restore selections if they still exist
        origin_index = self.filter_origin.findText(current_origin)
        if origin_index >= 0:
            self.filter_origin.setCurrentIndex(origin_index)
            
        status_index = self.filter_status.findText(current_status)
        if status_index >= 0:
            self.filter_status.setCurrentIndex(status_index)
    
    def apply_filters(self):
        awb_filter = self.filter_awb.text().lower()
        origin_filter = self.filter_origin.currentText()
        status_filter = self.filter_status.currentText()
        
        for row in range(self.results_table.rowCount()):
            show_row = True
            
            # Apply each filter
            if awb_filter and awb_filter not in self.results_table.item(row, 0).text().lower():
                show_row = False
                
            if origin_filter != "All Origins" and self.results_table.item(row, 1).text() != origin_filter:
                show_row = False
                
            if status_filter != "All Statuses" and self.results_table.item(row, 3).text() != status_filter:
                show_row = False
                
            self.results_table.setRowHidden(row, not show_row)
    
    def export_data(self, source_table=None):
        # Safeguard: if invalid object is passed
        if not hasattr(source_table, "rowCount"):
            source_table = self.results_table
            
        # Get visible rows only
        visible_rows = []
        for row in range(source_table.rowCount()):
            if not source_table.isRowHidden(row):
                row_data = []
                for col in range(source_table.columnCount()):
                    row_data.append(source_table.item(row, col).text())
                visible_rows.append(row_data)
        
        if not visible_rows:
            QMessageBox.warning(self, "Export Error", "No data to export.")
            return
        
        # Ask user for file location
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Data", "", "CSV Files (*.csv);;Excel Files (*.xlsx)"
        )
        
        if not filename:
            return
        
        # Export as CSV
        if filename.endswith('.csv'):
            try:
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    # Write header
                    writer.writerow(["AWB", "Origin", "Destination", "Status", "Timestamp"])
                    # Write data
                    writer.writerows(visible_rows)
                
                QMessageBox.information(self, "Export Successful", f"Data exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Error exporting data: {str(e)}")
        
        # Export as Excel
        elif filename.endswith('.xlsx'):
            try:
                import pandas as pd
                
                # Convert to pandas DataFrame
                df = pd.DataFrame(visible_rows, columns=["AWB", "Origin", "Destination", "Status", "Timestamp"])
                
                # Export to Excel
                df.to_excel(filename, index=False)
                
                QMessageBox.information(self, "Export Successful", f"Data exported to {filename}")
            except ImportError:
                QMessageBox.critical(self, "Export Error", "Excel export requires pandas. Please install it.")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Error exporting data: {str(e)}")
    
    def export_cache_data(self):
        self.export_data(self.cache_table)
    
    def apply_cache_filters(self):
        awb_filter = self.cache_filter_awb.text().lower()
        origin_filter = self.cache_filter_origin.currentText()
        status_filter = self.cache_filter_status.currentText()
        
        for row in range(self.cache_table.rowCount()):
            show_row = True
            
            if awb_filter and awb_filter not in self.cache_table.item(row, 0).text().lower():
                show_row = False
                
            if origin_filter != "All Origins" and self.cache_table.item(row, 1).text() != origin_filter:
                show_row = False
                
            if status_filter != "All Statuses" and self.cache_table.item(row, 3).text() != status_filter:
                show_row = False
                
            self.cache_table.setRowHidden(row, not show_row)

    def clear_cache(self):
        confirm = QMessageBox.question(
            self, "Confirm Cache Clear",
            "Are you sure you want to clear the cache?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.cache_data = []
            self.save_cache()
            self.update_cache_display()
            self.statusBar().showMessage("Cache cleared", 3000)

    def update_cache_display(self):
        self.cache_table.setRowCount(len(self.cache_data))
        for row, data in enumerate(self.cache_data):
            for col, value in enumerate([
                data['awb'],
                data['origin'],
                data['destination'],
                data['status'],
                data['timestamp'],
                data.get('delivered_on', 'N/A')
            ]):
                item = QTableWidgetItem(value)
                self.cache_table.setItem(row, col, item)
        self.cache_count_label.setText(str(len(self.cache_data)))
        self.update_cache_filter_options()


    def update_cache_filter_options(self):
        current_origin = self.cache_filter_origin.currentText()
        current_status = self.cache_filter_status.currentText()

        self.cache_filter_origin.clear()
        self.cache_filter_status.clear()

        self.cache_filter_origin.addItem("All Origins")
        self.cache_filter_status.addItem("All Statuses")

        origins = set(entry['origin'] for entry in self.cache_data)
        statuses = set(entry['status'] for entry in self.cache_data)

        for origin in sorted(origins):
            self.cache_filter_origin.addItem(origin)

        for status in sorted(statuses):
            self.cache_filter_status.addItem(status)

        index = self.cache_filter_origin.findText(current_origin)
        if index >= 0:
            self.cache_filter_origin.setCurrentIndex(index)

        index = self.cache_filter_status.findText(current_status)
        if index >= 0:
            self.cache_filter_status.setCurrentIndex(index)

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_cache(self):
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.cache_data, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Cache Error", f"Failed to save cache: {str(e)}")

    def save_settings(self):
        settings = {
            "cache_enabled": self.cache_enabled.isChecked(),
            "cache_days": self.cache_days.currentText(),
            "api_timeout": self.api_timeout.currentText(),
            "retry_count": self.retry_count.currentText()
        }
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
            QMessageBox.information(self, "Settings", "Settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Settings Error", f"Failed to save settings: {str(e)}")

def main():
    app = QApplication(sys.argv)
    tracker = AWBTrackerApp()
    tracker.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

import sys
import json
import csv
import os
from datetime import datetime
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QComboBox, QTextEdit, QMessageBox, QDialog,
                             QFormLayout, QCheckBox, QFileDialog, QGroupBox, QProgressBar, 
                             QSplitter, QMenu)
from PyQt5.QtGui import QFont, QIcon, QTextCharFormat, QColor, QDesktopServices
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QUrl
import urllib3
import time
from collections import Counter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

APP_NAME = "DHL Tracker"
APP_VERSION = "2.2"
SETTINGS_FILE = "settings.json"
CACHE_FILE = "cache.json"

API_ENDPOINT = "https://api-eu.dhl.com/track/shipments"

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
                self.progress.emit(int((i + 1 / total) * 100))

                result = self.api_client.track_shipment(awb)

                if result and result.get("status", "").lower() != "unavailable":
                    results.append(result)

                if i < total - 1:
                    time.sleep(1)
            except Exception as e:
                self.error.emit(f"Error tracking AWB {awb}: {str(e)}")

        self.progress.emit(100)
        self.finished.emit(results)

class TrackingApiClient:
    def __init__(self, user_label, api_key):
        self.user_label = user_label
        self.api_key = api_key
        self.base_url = API_ENDPOINT

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
            verify=False  
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
        
        events = shipment.get("events", [])
        last_event = events[0] if events else {}
        last_status = last_event.get("statusCode", "N/A").capitalize()
        last_timestamp = last_event.get("timestamp", "")

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

        proof_of_delivery_url = "N/A"

        details = shipment.get("details", {})
        if "proofOfDelivery" in details:
            proof_of_delivery_url = details["proofOfDelivery"].get("documentUrl", "N/A")

        eta_raw = shipment.get("estimatedTimeOfDelivery", "N/A")
        try:
            eta_fmt = datetime.fromisoformat(eta_raw).strftime('%Y-%m-%d %H:%M:%S') if eta_raw != "N/A" else "N/A"
        except ValueError:
            eta_fmt = eta_raw

        return {
            'awb': awb,
            'origin': shipment.get("origin", {}).get("address", {}).get("addressLocality", "UNKNOWN"),
            'destination': shipment.get("destination", {}).get("address", {}).get("addressLocality", "UNKNOWN"),
            'status': last_status,
            'timestamp': last_timestamp_fmt,
            'delivered_on': delivered_fmt,
            'proof_of_delivery': proof_of_delivery_url,
            'events_full': events,
            'eta': eta_fmt
}

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.setMinimumWidth(300)

        self.sites = ["x", "y", "z"]

        self.api_keys = {
            "Primary": "",
            "Backup": ""
        }

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.site_selector = QComboBox()
        self.site_selector.addItems(self.sites)

        self.api_selector = QComboBox()
        self.api_selector.addItems(["Primary", "Backup"])

        form_layout.addRow("Select Site:", self.site_selector)
        form_layout.addRow("API Account:", self.api_selector)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.login_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def accept(self):
        self.selected_site = self.site_selector.currentText()
        self.selected_api = self.api_keys[self.api_selector.currentText()]
        super().accept()

class RichTextEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        
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

class TrackingHistoryDialog(QDialog):
    def __init__(self, awb, history_events, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Tracking History: {awb}")
        self.setMinimumSize(800, 400)

        layout = QVBoxLayout()

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)

        html = "<h2>Tracking Events</h2><ul style='font-family: monospace;'>"
        for event in history_events:
            time_str = event.get("timestamp", "N/A")
            location = event.get("location", {}).get("address", {}).get("addressLocality", "Unknown Location")
            description = event.get("description", "No Description")
            html += f"<li><b>{time_str}</b> — {description} <i>({location})</i></li>"
        html += "</ul>"

        self.text_area.setHtml(html)

        layout.addWidget(self.text_area)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        self.setLayout(layout)

class AWBTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(800, 600)

        self.comments_data = self.load_comments()
        self.current_awb_in_focus = None
        
        login_dialog = LoginDialog(self)
        if login_dialog.exec_() == QDialog.Accepted:
            self.current_user = login_dialog.selected_site
            self.current_api = login_dialog.selected_api
            self.api_client = TrackingApiClient(self.current_user, self.current_api)
        else:
            sys.exit()
        
        self.cache_data = self.load_cache()
        
        self.init_ui()

    def handle_results_double_click(self, row, column):
        if column == 0: 
            item = self.results_table.item(row, 0)
            if item is None:
                QMessageBox.warning(self, "Selection Error", "No AWB found in the selected row.")
                return
            
            awb = item.text()

            shipment = next((s for s in self.cache_data if s['awb'] == awb), None)
            if not shipment:
                QMessageBox.information(self, "No Data", f"No tracking history found for AWB {awb}")
                return

            tracking_history = shipment.get("events_full", [])
            if not tracking_history:
                QMessageBox.information(self, "No Events", f"No tracking events found for AWB {awb}")
                return

            dialog = TrackingHistoryDialog(awb, tracking_history, self)
            dialog.exec_()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout()
        
        self.statusBar().showMessage(f"Logged in as: {self.current_user}")
        
        self.tabs = QTabWidget()
        self.tracking_tab = QWidget()
        self.cache_tab = QWidget()
        self.settings_tab = QWidget()
        self.about_tab = QWidget()
        
        self.setup_tracking_tab()
        self.setup_cache_tab()
        self.setup_settings_tab()
        self.setup_about_tab()
        
        self.tabs.addTab(self.tracking_tab, "Tracking")
        self.tabs.addTab(self.cache_tab, "Cache")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.about_tab, "About")
        
        main_layout.addWidget(self.tabs)
        self.central_widget.setLayout(main_layout)
    
    def setup_tracking_tab(self):
        layout = QVBoxLayout()

        search_layout = QHBoxLayout()
        self.awb_input = QLineEdit()
        self.awb_input.setPlaceholderText("Enter AWB number(s) - separate multiple with commas")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_awb)
        search_layout.addWidget(QLabel("AWB:"))
        search_layout.addWidget(self.awb_input)
        search_layout.addWidget(search_button)

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
        export_button = QPushButton("Export Data")
        export_button.clicked.connect(self.export_data)
        filter_layout.addWidget(QLabel("Filter:"))
        filter_layout.addWidget(self.filter_awb)
        filter_layout.addWidget(self.filter_origin)
        filter_layout.addWidget(self.filter_status)
        filter_layout.addWidget(export_button)

        layout.addLayout(search_layout)
        layout.addLayout(filter_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        top_widget = QWidget()
        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels(["AWB", "Origin", "Destination", "Status", "Delivered On", "ETA", "Proof of Delivery"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.cellDoubleClicked.connect(self.handle_results_double_click)
        self.results_table.cellClicked.connect(self.handle_pod_click)
        self.results_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self.show_table_context_menu)

        self.summary_label = QLabel("Total Shipments: 0")
        self.summary_label.setAlignment(Qt.AlignRight)
        self.summary_label.setStyleSheet("font-weight: bold; padding: 5px;")

        top_layout.addWidget(self.results_table)
        top_layout.addWidget(self.summary_label)
        top_widget.setLayout(top_layout)

        comment_widget = QWidget()
        comment_layout = QVBoxLayout()
        comment_label_layout = QHBoxLayout()

        comment_label_layout.addWidget(QLabel("Comment for Selected AWB:"))
        comment_label_layout.addStretch()

        self.comment_editor = QTextEdit()
        self.comment_editor.setPlaceholderText("Enter comment for selected AWB")

        save_comment_btn = QPushButton("Save Comment")
        save_comment_btn.setMaximumWidth(150)
        save_comment_btn.clicked.connect(self.save_current_comment)

        comment_layout.addLayout(comment_label_layout)
        comment_layout.addWidget(self.comment_editor)
        comment_layout.addWidget(save_comment_btn)
        comment_widget.setLayout(comment_layout)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(comment_widget)

        splitter.setSizes([600, 100])

        layout.addWidget(splitter)

        self.tracking_tab.setLayout(layout)

        self.results_table.itemSelectionChanged.connect(self.load_selected_awb_comment)


    def show_table_context_menu(self, position):
        index = self.results_table.indexAt(position)
        if not index.isValid():
            return

        row = index.row()
        awb_item = self.results_table.item(row, 0)
        pod_item = self.results_table.item(row, 6)

        if awb_item is None:
            return

        awb = awb_item.text()
        pod_link = pod_item.text() if pod_item else "N/A"

        menu = QMenu(self)

        view_history_action = menu.addAction("View Tracking History")
        copy_awb_action = menu.addAction("Copy AWB")
        comment_action = menu.addAction("Add/Edit Comment")
        if pod_link and pod_link != "N/A":
            pod_action = menu.addAction("Open Proof of Delivery")

        action = menu.exec_(self.results_table.viewport().mapToGlobal(position))

        if action == view_history_action:
            self.handle_results_double_click(row, 0)

        elif action == copy_awb_action:
            QApplication.clipboard().setText(awb)

        elif action == comment_action:
            self.results_table.selectRow(row)
            self.load_selected_awb_comment()
            self.comment_editor.setFocus()

        elif pod_link and pod_link != "N/A" and action == pod_action:
            QDesktopServices.openUrl(QUrl(pod_link))

    def handle_pod_click(self, row, column):
        if column == 6: 
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ControlModifier:
                item = self.results_table.item(row, column)
                url = item.text()
                if url.startswith("http"):
                    import webbrowser
                    webbrowser.open(url)
    
    def setup_cache_tab(self):
        layout = QVBoxLayout()
        
        info_layout = QHBoxLayout()
        self.cache_count_label = QLabel(str(len(self.cache_data)))
        
        info_layout.addWidget(QLabel("Cached Shipments:"))
        info_layout.addWidget(self.cache_count_label)
        info_layout.addStretch()
        
        clear_cache_button = QPushButton("Clear Cache")
        clear_cache_button.clicked.connect(self.clear_cache)
        info_layout.addWidget(clear_cache_button)
        
        layout.addLayout(info_layout)
        
        self.cache_table = QTableWidget()
        self.cache_table.setColumnCount(6)
        self.cache_table.setHorizontalHeaderLabels(["AWB", "Origin", "Destination", "Status", "Last Update", "Delivered On"])
        self.cache_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.cache_table)
        
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
        
        self.update_cache_display()
    
    def setup_settings_tab(self):
        layout = QVBoxLayout()
        
        user_group = QGroupBox("User Information")
        user_layout = QFormLayout()
        
        self.current_user_label = QLabel(self.current_user)
        
        api_layout = QHBoxLayout()
        self.api_key_label = QLineEdit(self.current_api)
        self.api_key_label.setEchoMode(QLineEdit.Password)
        self.api_key_label.setReadOnly(True)
        
        self.toggle_api_visibility = QPushButton("Show")
        self.toggle_api_visibility.clicked.connect(self.toggle_api_key_visibility)
        
        api_layout.addWidget(self.api_key_label)
        api_layout.addWidget(self.toggle_api_visibility)
        
        self.endpoint_label = QLineEdit(API_ENDPOINT)
        self.endpoint_label.setReadOnly(True)
        
        user_layout.addRow("Current User:", self.current_user_label)
        user_layout.addRow("API Key:", api_layout)
        user_layout.addRow("API Endpoint:", self.endpoint_label)
        
        user_group.setLayout(user_layout)
        layout.addWidget(user_group)
        
        app_settings_group = QGroupBox("Application Settings")
        settings_layout = QFormLayout()
        
        self.cache_enabled = QCheckBox()
        self.cache_enabled.setChecked(True)
        
        self.cache_days = QComboBox()
        for days in [1, 3, 7, 14, 30]:
            self.cache_days.addItem(f"{days} days")
        self.cache_days.setCurrentIndex(2)
        
        self.api_timeout = QComboBox()
        for timeout in [10, 20, 30, 60]:
            self.api_timeout.addItem(f"{timeout} seconds")
        self.api_timeout.setCurrentIndex(2)
        
        self.retry_count = QComboBox()
        for count in [0, 1, 2, 3]:
            self.retry_count.addItem(f"{count} retries")
        self.retry_count.setCurrentIndex(1)  
        
        settings_layout.addRow("Enable Cache:", self.cache_enabled)
        settings_layout.addRow("Cache Duration:", self.cache_days)
        settings_layout.addRow("API Timeout:", self.api_timeout)
        settings_layout.addRow("Connection Retries:", self.retry_count)
        
        app_settings_group.setLayout(settings_layout)
        layout.addWidget(app_settings_group)
        
        save_settings_button = QPushButton("Save Settings")
        save_settings_button.clicked.connect(self.save_settings)

        layout.addWidget(save_settings_button)
        layout.addStretch()
        
        self.settings_tab.setLayout(layout)
    
    def setup_about_tab(self):
        layout = QVBoxLayout()
        
        about_text = f"""
        <h1>{APP_NAME} v{APP_VERSION}</h1>
        <p>An application for tracking DHL shipments.</p>
        <p><b>Features:</b></p>
        <ul>
            <li>Search for multiple AWB tracking numbers</li>
            <li>View shipment details including origin, destination, status, timestamp, and history</li>
            <li>Filter data by AWB, Origin, and Status</li>
            <li>Persistent caching tracking information to reduce API calls</li>
            <li>Export data to CSV</li>
            <li>Persistent comments section</li>
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

    def search_awb(self):
        awb_input = self.awb_input.text().strip()
        if not awb_input:
            QMessageBox.warning(self, "Input Error", "Please enter at least one AWB number.")
            return
        
        awb_list = [awb.strip() for awb in awb_input.split(',') if awb.strip()]
        
        self.results_table.setRowCount(0)
        
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
        
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(bool(remaining_awbs))
        
        if remaining_awbs:
            self.api_worker = ApiWorker(self.api_client, remaining_awbs)
            self.api_worker.progress.connect(self.update_progress)
            self.api_worker.finished.connect(lambda results: self.process_api_results(results, found_in_cache))
            self.api_worker.error.connect(self.show_api_error)
            self.api_worker.start()
        else:
            self.display_results(found_in_cache)
            self.update_filter_options(found_in_cache)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def show_api_error(self, error_message):
        self.statusBar().showMessage(error_message, 5000)
    
    def process_api_results(self, api_results, cache_results):
        self.progress_bar.setVisible(False)
        
        if self.cache_enabled.isChecked() and api_results:
            existing_awbs = {entry['awb'] for entry in self.cache_data}
            new_entries = [r for r in api_results if r['awb'] not in existing_awbs]
            self.cache_data.extend(new_entries)
            self.save_cache()
            self.update_cache_display()
        
        all_results = cache_results + api_results
        
        self.display_results(all_results)
        
        self.update_filter_options(all_results)
        
        if all_results:
            self.statusBar().showMessage(f"Found {len(all_results)} shipments", 3000)
        else:
            self.statusBar().showMessage("No shipments found", 3000)
    
    def display_results(self, results):
        self.results_table.setRowCount(len(results))

        color_map = {
            'delivered': QColor(200, 255, 200),  # Light green
            'transit': QColor(230, 230, 255),    # Light blue
            'delayed': QColor(255, 200, 200),    # Light red
            'exception': QColor(255, 200, 200)   # Light red
        }

        comment_bg_color = QColor(255, 255, 180)  # Light yellow for rows with comments

        for row, data in enumerate(results):
            row_values = [
                data.get('awb', 'N/A'),
                data.get('origin', 'UNKNOWN'),
                data.get('destination', 'UNKNOWN'),
                data.get('status', 'N/A'),
                data.get('delivered_on', 'N/A'),
                data.get('eta', 'N/A'),
                data.get('proof_of_delivery', 'N/A')
            ]

            for col, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                if col == 6 and value != "N/A":
                    item.setForeground(QColor('blue'))
                    font = item.font()
                    font.setUnderline(True)
                    item.setFont(font)
                    item.setToolTip("Ctrl+Click to open POD link")
                self.results_table.setItem(row, col, item)

            status = data.get('status', '').lower()
            for status_key, color in color_map.items():
                if status_key in status:
                    for col in range(len(row_values)):
                        item = self.results_table.item(row, col)
                        if item:
                            item.setBackground(color)
                    break

            awb = data.get('awb', '')
            if awb in self.comments_data:
                for col in range(6):
                    item = self.results_table.item(row, col)
                    if item:
                        item.setBackground(comment_bg_color)

        self.summary_label.setText(f"Total Shipments: {len(results)}")
    
    def update_filter_options(self, results):
        current_origin = self.filter_origin.currentText()
        current_status = self.filter_status.currentText()
        
        self.filter_origin.clear()
        self.filter_status.clear()
        
        self.filter_origin.addItem("All Origins")
        self.filter_status.addItem("All Statuses")
        
        origins = set(data['origin'] for data in results)
        statuses = set(data['status'] for data in results)
        
        for origin in sorted(origins):
            self.filter_origin.addItem(origin)
        
        for status in sorted(statuses):
            self.filter_status.addItem(status)
        
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

            awb_item = self.results_table.item(row, 0)
            origin_item = self.results_table.item(row, 1)
            status_item = self.results_table.item(row, 3)

            if awb_filter:
                if awb_item is None or awb_filter not in awb_item.text().lower():
                    show_row = False

            if origin_filter != "All Origins":
                if origin_item is None or origin_item.text() != origin_filter:
                    show_row = False

            if status_filter != "All Statuses":
                if status_item is None or status_item.text() != status_filter:
                    show_row = False

            self.results_table.setRowHidden(row, not show_row)

        visible_rows = sum(not self.results_table.isRowHidden(row) for row in range(self.results_table.rowCount()))
        self.summary_label.setText(f"Total Shipments: {visible_rows}")
    
    def export_data(self, source_table=None):
        if not hasattr(source_table, "rowCount"):
            source_table = self.results_table

        visible_rows = []
        for row in range(source_table.rowCount()):
            if not source_table.isRowHidden(row):
                row_data = []
                for col in range(source_table.columnCount()):
                    row_data.append(source_table.item(row, col).text())

                awb = source_table.item(row, 0).text()
                comment = self.comments_data.get(awb, "")
                row_data.append(comment)

                visible_rows.append(row_data)

        if not visible_rows:
            QMessageBox.warning(self, "Export Error", "No data to export.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Data", "", "CSV Files (*.csv);;Excel Files (*.xlsx)"
        )

        if not filename:
            return

        headers = ["AWB", "Origin", "Destination", "Status", "Timestamp", "Comments"]

        if filename.endswith('.csv'):
            try:
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(headers)
                    writer.writerows(visible_rows)
                QMessageBox.information(self, "Export Successful", f"Data exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Error exporting data: {str(e)}")

        elif filename.endswith('.xlsx'):
            try:
                import pandas as pd
                df = pd.DataFrame(visible_rows, columns=headers)
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
    
    def load_selected_awb_comment(self):
        selected = self.results_table.selectedItems()
        if selected:
            awb = selected[0].text()
            self.current_awb_in_focus = awb
            self.comment_editor.setText(self.comments_data.get(awb, ""))

    def save_current_comment(self):
        if self.current_awb_in_focus:
            comment = self.comment_editor.toPlainText().strip()
            if comment:
                self.comments_data[self.current_awb_in_focus] = comment
            elif self.current_awb_in_focus in self.comments_data:
                del self.comments_data[self.current_awb_in_focus]
            self.save_comments()

    def load_comments(self):
        if os.path.exists("comments.json"):
            try:
                with open("comments.json", "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_comments(self):
        try:
            with open("comments.json", "w") as f:
                json.dump(self.comments_data, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Comment Save Error", f"Failed to save comment: {str(e)}")

def main():
    app = QApplication(sys.argv)
    tracker = AWBTrackerApp()
    tracker.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

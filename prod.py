import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font
from PIL import Image, ImageTk
import requests
import ssl
import json
import csv
import urllib3
from datetime import datetime
from openpyxl import Workbook

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DHLTrackingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DHL Tracking App")
        self.root.geometry("1000x650")

        self.data = []
        self.sorted_by_column = ""
        self.sort_reverse = False

        self.style = ttk.Style()
        self.style.configure("Treeview", background="white", foreground="black", rowheight=25, fieldbackground="white")
        self.style.configure("Treeview.Heading", font=('Arial', 10, 'bold'), background="#f0f0f0", foreground="black")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True)

        self.track_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.track_frame, text="Tracking")

        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")

        self.about_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.about_frame, text="About")

        top_frame = ttk.Frame(self.track_frame)
        top_frame.pack(fill='x', pady=10, padx=10)

        original_image = Image.open(r"C:\Users\aa83w\Documents\Projects\DHL\Cummins.png")
        width, height = original_image.size
        new_size = (int(width * 0.2), int(height * 0.2))
        resized_image = original_image.resize(new_size, Image.Resampling.LANCZOS)
        self.logo_image = ImageTk.PhotoImage(resized_image)
        logo_label = ttk.Label(top_frame, image=self.logo_image)
        logo_label.pack(side='left', padx=(0, 20))

        search_frame = ttk.Frame(top_frame)
        search_frame.pack(side='left', fill='x', expand=True)

        self.search_label = ttk.Label(search_frame, text="Enter AWB(s):")
        self.search_label.pack(anchor='w')

        self.search_entry = ttk.Entry(search_frame, width=50)
        self.search_entry.pack(fill='x', pady=2)

        self.search_button = ttk.Button(search_frame, text="Search", command=self.search)
        self.search_button.pack(pady=2, anchor='w')

        self.treeview = ttk.Treeview(self.track_frame, columns=("AWB", "Origin", "Destination", "Status", "Timestamp"), show="headings", style="Treeview")
        self.treeview.pack(fill='both', expand=True, padx=10, pady=10)

        for col in ("AWB", "Origin", "Destination", "Status", "Timestamp"):
            self.treeview.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
            self.treeview.column(col, width=180, anchor="center")

        filter_and_button_frame = ttk.Frame(self.track_frame)
        filter_and_button_frame.pack(fill='x', padx=10, pady=5)

        dropdown_filters_frame = ttk.Frame(filter_and_button_frame)
        dropdown_filters_frame.pack(side='left', padx=10)

        filter_title_label = ttk.Label(dropdown_filters_frame, text="Filter by:", font=("Arial", 10, "bold"))
        filter_title_label.pack(side='top', padx=5)

        self.filters = {}
        self.filter_vars = {}

        for col in ["AWB", "Origin", "Status"]:
            var = tk.StringVar()
            self.filter_vars[col] = var
            self.filters[col] = ttk.Combobox(dropdown_filters_frame, textvariable=var, state="readonly", width=20)
            self.filters[col].pack(side='top', padx=5)
            self.filters[col].bind("<<ComboboxSelected>>", self.apply_filters)

        note_area_frame = ttk.Frame(self.track_frame)
        note_area_frame.pack(side='left', padx=10, pady=10)

        self.notes_label = ttk.Label(note_area_frame, text="Notes:", font=("Arial", 10, "bold"))
        self.notes_label.pack(anchor="w")

        self.notes_text = tk.Text(note_area_frame, height=10, width=30)
        self.notes_text.pack(padx=5, pady=5)

        self.bold_button = ttk.Button(note_area_frame, text="Bold", command=lambda: self.toggle_font_style("bold"))
        self.bold_button.pack(side="left", padx=5)
        self.italic_button = ttk.Button(note_area_frame, text="Italics", command=lambda: self.toggle_font_style("italic"))
        self.italic_button.pack(side="left", padx=5)
        self.underline_button = ttk.Button(note_area_frame, text="Underline", command=lambda: self.toggle_font_style("underline"))
        self.underline_button.pack(side="left", padx=5)

        right_buttons_frame = ttk.Frame(filter_and_button_frame)
        right_buttons_frame.pack(side='right', padx=10, pady=10)

        self.download_button = ttk.Button(right_buttons_frame, text="Download", command=self.download_csv)
        self.download_button.pack(pady=5)

        self.clear_button = ttk.Button(right_buttons_frame, text="Clear Data", command=self.clear_data)
        self.clear_button.pack(pady=5)

        settings_label = ttk.Label(self.settings_frame, text="Settings", font=("Arial", 12, "bold"))
        settings_label.pack(pady=10)

        self.export_format_label = ttk.Label(self.settings_frame, text="Export Format:")
        self.export_format_label.pack(pady=10)
        self.export_format_var = tk.StringVar(value="CSV")
        self.export_format_menu = ttk.Combobox(self.settings_frame, textvariable=self.export_format_var, values=["CSV", "Excel"], state="readonly")
        self.export_format_menu.pack(pady=5)

        self.export_columns_label = ttk.Label(self.settings_frame, text="Select Columns to Export:")
        self.export_columns_label.pack(pady=10)

        self.column_check_vars = {
            "AWB": tk.BooleanVar(value=True),
            "Origin": tk.BooleanVar(value=True),
            "Destination": tk.BooleanVar(value=True),
            "Status": tk.BooleanVar(value=True),
            "Timestamp": tk.BooleanVar(value=True)
        }

        for col, var in self.column_check_vars.items():
            ttk.Checkbutton(self.settings_frame, text=col, variable=var).pack(anchor="w", padx=5)

        about_text = "DHL Shipment Tracker\nVersion 1.0\nDeveloped by Sumit Chaturvedi, Cummins UK\nFor internal shipment visibility and tracking."
        about_label = ttk.Label(self.about_frame, text=about_text, font=("Arial", 10))
        about_label.pack(padx=5, pady=5)

    def toggle_font_style(self, style):
        current_tags = self.notes_text.tag_names("sel.first")
        if style == "bold":
            if "bold" in current_tags:
                self.notes_text.tag_remove("bold", "sel.first", "sel.last")
            else:
                self.notes_text.tag_add("bold", "sel.first", "sel.last")
                bold_font = font.Font(self.notes_text, self.notes_text.cget("font"))
                bold_font.config(weight="bold")
                self.notes_text.tag_configure("bold", font=bold_font)
        elif style == "italic":
            if "italic" in current_tags:
                self.notes_text.tag_remove("italic", "sel.first", "sel.last")
            else:
                self.notes_text.tag_add("italic", "sel.first", "sel.last")
                italic_font = font.Font(self.notes_text, self.notes_text.cget("font"))
                italic_font.config(slant="italic")
                self.notes_text.tag_configure("italic", font=italic_font)
        elif style == "underline":
            if "underline" in current_tags:
                self.notes_text.tag_remove("underline", "sel.first", "sel.last")
            else:
                self.notes_text.tag_add("underline", "sel.first", "sel.last")
                underline_font = font.Font(self.notes_text, self.notes_text.cget("font"))
                underline_font.config(underline=True)
                self.notes_text.tag_configure("underline", font=underline_font)

    def search(self):
        awbs = self.search_entry.get().split(',')
        awbs = [awb.strip() for awb in awbs if awb.strip()]

        all_data = []
        for awb in awbs:
            url = f"https://api-eu.dhl.com/track/shipments?trackingNumber={awb}"
            headers = {'DHL-API-Key': 'Q1msFzziSbBq4qiqgqnQHy1aaWrZK5ow'}
            try:
                response = requests.get(url, headers=headers, verify=False)
                if response.status_code == 200:
                    data = response.json()
                    all_data.extend(data.get("shipments", []))
                elif response.status_code == 429:
                    messagebox.showerror("Rate Limit", "Rate limit exceeded. Please wait and try again later.")
                    return
                else:
                    messagebox.showerror("Error", f"Failed to fetch data for AWB {awb}. Status Code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                messagebox.showerror("Error", f"An error occurred: {e}")

        self.data = all_data
        self.display_data(self.data)

    def display_data(self, shipments):
        for row in self.treeview.get_children():
            self.treeview.delete(row)

        dropdown_values = {"AWB": set(), "Origin": set(), "Status": set()}

        for shipment in shipments:
            shipment_id = shipment.get('id', 'N/A')
            origin = shipment.get('destination', {}).get('address', {}).get('addressLocality', 'N/A')
            destination = shipment.get('origin', {}).get('address', {}).get('addressLocality', 'N/A')
            status = shipment.get('status', {}).get('statusCode', 'N/A')
            timestamp = shipment.get('status', {}).get('timestamp', 'N/A')

            self.treeview.insert("", "end", values=(shipment_id, origin, destination, status, timestamp))

            dropdown_values["AWB"].add(shipment_id)
            dropdown_values["Origin"].add(origin)
            dropdown_values["Status"].add(status)

        for col in dropdown_values:
            values = sorted(dropdown_values[col])
            self.filters[col]['values'] = ['All'] + values
            self.filter_vars[col].set('All')

    def extract_column_value(self, item, col):
        if col == "AWB":
            return item.get("id", "")
        elif col == "Origin":
            return item.get('destination', {}).get('address', {}).get('addressLocality', '')
        elif col == "Destination":
            return item.get('origin', {}).get('address', {}).get('addressLocality', '')
        elif col == "Status":
            return item.get("status", {}).get("statusCode", "")
        elif col == "Timestamp":
            return item.get("status", {}).get("timestamp", "")
        return ""

    def download_csv(self):
        file_format = self.export_format_var.get()
        selected_columns = [col for col, var in self.column_check_vars.items() if var.get()]

        if not selected_columns:
            messagebox.showwarning("No Columns Selected", "Please select at least one column to export.")
            return

        filetypes = [("CSV Files", "*.csv")] if file_format == "CSV" else [("Excel Files", "*.xlsx")]
        default_ext = ".csv" if file_format == "CSV" else ".xlsx"

        file_path = filedialog.asksaveasfilename(defaultextension=default_ext, filetypes=filetypes)
        if not file_path:
            return

        if file_format == "CSV":
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(selected_columns)

                for shipment in self.data:
                    row = [self.extract_column_value(shipment, col) for col in selected_columns]
                    writer.writerow(row)

        elif file_format == "Excel":
            wb = Workbook()
            ws = wb.active
            ws.append(selected_columns)

            for shipment in self.data:
                row = [self.extract_column_value(shipment, col) for col in selected_columns]
                ws.append(row)

            wb.save(file_path)

    def apply_filters(self, event=None):
        filtered_data = self.data

        for col, var in self.filter_vars.items():
            filter_value = var.get()
            if filter_value != "All":
                filtered_data = [row for row in filtered_data if self.extract_column_value(row, col) == filter_value]

        self.display_data(filtered_data)

    def sort_by_column(self, column):
        reverse = self.sorted_by_column == column and not self.sort_reverse
        self.sorted_by_column = column
        self.sort_reverse = reverse
        self.data.sort(key=lambda x: self.extract_column_value(x, column), reverse=reverse)
        self.display_data(self.data)

    def clear_data(self):
        self.data.clear()
        self.treeview.delete(*self.treeview.get_children())

root = tk.Tk()
app = DHLTrackingApp(root)
root.mainloop()

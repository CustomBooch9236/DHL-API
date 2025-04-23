import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import http.client
import urllib.parse
import json
import ssl
import time
from datetime import datetime
import pandas as pd
from PIL import Image, ImageTk
import threading

ssl._create_default_https_context = ssl._create_unverified_context

location_to_site = {
    'BIRMINGHAM - UK': 'DAV',
    'TEESSIDE - UK': 'DEP',
    'LEEDS - UK': 'CTT'
}

API_KEY = '' #enter your API key
cache = {}

window = tk.Tk()
window.title("DHL Shipment Tracker")
window.geometry("1000x700")
window.configure(bg='#F8EFD8')

auto_refresh_enabled = tk.BooleanVar(value=True)

logo_path = r"" #file path
logo_image = Image.open(logo_path).resize((100, 100), Image.Resampling.LANCZOS)
logo_tk = ImageTk.PhotoImage(logo_image)
tk.Label(window, image=logo_tk, bg='#F8EFD8').place(x=10, y=10)

tk.Label(window, text="Enter Tracking Numbers (comma separated):", fg="black", bg="#F8EFD8").pack(pady=(70, 0))
tracking_numbers_entry = tk.Entry(window, width=70, fg="black", bg="white")
tracking_numbers_entry.pack()

button_frame = tk.Frame(window, bg='#F8EFD8')
button_frame.pack(pady=10)

track_button = tk.Button(button_frame, text="Track Shipments", command=lambda: process_tracking_numbers(), fg='white', bg='#c6171e')
track_button.pack(side="left", padx=5)

download_button = tk.Button(button_frame, text="Download CSV", command=lambda: ask_download(), fg='white', bg='#c6171e')
download_button.pack(side="left", padx=5)

notebook = ttk.Notebook(window)
notebook.pack(fill="both", expand=True, padx=10, pady=10)

results_tab = tk.Frame(notebook, bg='#F8EFD8')
cache_tab = tk.Frame(notebook, bg='#F8EFD8')
settings_tab = tk.Frame(notebook, bg='#F8EFD8')
about_tab = tk.Frame(notebook, bg='#F8EFD8')
notebook.add(results_tab, text="Tracking Results")
notebook.add(cache_tab, text="Cached Data")
notebook.add(settings_tab, text="Settings")
notebook.add(about_tab, text="About")

columns = ["Site", "Tracking Number", "Status", "Delivered On", "ETA"]
treeview = ttk.Treeview(results_tab, columns=columns, show="headings")
cache_table = ttk.Treeview(cache_tab, columns=columns, show="headings")

for col in columns:
    treeview.heading(col, text=col, command=lambda c=col: sort_column(treeview, c))
    treeview.column(col, width=140, anchor="center")
    cache_table.heading(col, text=col)
    cache_table.column(col, width=140, anchor="center")

filter_frame = tk.Frame(results_tab, bg='#F8EFD8')
filter_frame.pack(pady=10)

filter_options = {}
filter_buttons = {}

def show_multiselect(col):
    top = tk.Toplevel(window)
    top.title(f"{col} Filter")
    top.configure(bg="#F8EFD8")

    var_dict = {}
    for val in sorted({r[col] for r in cache.values()}):
        var = tk.BooleanVar()
        chk = tk.Checkbutton(top, text=val, variable=var, bg="#F8EFD8")
        chk.pack(anchor="w")
        var_dict[val] = var

    def apply_selection():
        selected = [val for val, var in var_dict.items() if var.get()]
        filter_options[col] = selected
        top.destroy()
        process_tracking_numbers()

    tk.Button(top, text="Apply", command=apply_selection, fg='white', bg='#c6171e').pack(pady=5)

for col in columns:
    btn = tk.Button(filter_frame, text=f"{col} Filter", command=lambda c=col: show_multiselect(c), fg='black', bg='#FFCC00')  
    btn.pack(side="left", padx=5)
    filter_buttons[col] = btn
    filter_options[col] = []

tk.Button(filter_frame, text="Clear Filters", command=lambda: clear_filters(), fg='black', bg='#FFCC00').pack(side="left", padx=5)

tk.Label(results_tab, text="Shipment Tracking Results", fg="black", bg="#F8EFD8", font=("Helvetica", 12, "bold")).pack(pady=10)

treeview.pack(pady=10, fill="both", expand=True)
cache_table.pack(pady=10, fill="both", expand=True)

notes_text = tk.Text(results_tab, height=5, fg="black", bg="white")
notes_text.pack(fill="x", padx=10, pady=(0, 10))
tk.Button(results_tab, text="Clear Notes", command=lambda: notes_text.delete("1.0", "end"), fg='white', bg='#c6171e').pack()

tk.Button(cache_tab, text="Load Cached Data", command=lambda: load_cache(), fg='white', bg='#c6171e').pack(pady=5)

tk.Label(settings_tab, text="Auto Refresh Interval (seconds):", fg="black", bg="#F8EFD8").pack(pady=(10, 0))
refresh_interval_entry = tk.Entry(settings_tab, fg="black", bg="white")
refresh_interval_entry.insert(0, "60")
refresh_interval_entry.pack()

tk.Checkbutton(settings_tab, text="Enable Auto Refresh", variable=auto_refresh_enabled, fg='black', bg="#F8EFD8").pack(pady=10)

about_text = "DHL Shipment Tracker\nVersion 1.1\nDeveloped by Sumit Chaturvedi, Cummins UK\nFor internal shipment visibility and tracking."
tk.Label(about_tab, text=about_text, justify="left", fg="black", bg="#F8EFD8").pack(padx=10, pady=10, anchor="nw")

def sort_column(tv, col):
    data = [(tv.set(k, col), k) for k in tv.get_children()]
    is_desc = getattr(tv, "_sorted_desc", {}).get(col, False)
    data.sort(reverse=not is_desc)
    for i, (val, k) in enumerate(data):
        tv.move(k, '', i)
    if not hasattr(tv, "_sorted_desc"):
        tv._sorted_desc = {}
    tv._sorted_desc[col] = not is_desc

def get_delivery_status(tracking_number, force_api=False):
    if tracking_number in cache and not force_api:
        return cache[tracking_number]

    connection = http.client.HTTPSConnection("api-eu.dhl.com")
    params = urllib.parse.urlencode({'trackingNumber': tracking_number, 'service': 'express'})
    headers = {'Accept': 'application/json', 'DHL-API-Key': API_KEY}

    try:
        connection.request("GET", f"/track/shipments?{params}", "", headers)
        response = connection.getresponse()
        data = json.loads(response.read())
    finally:
        connection.close()

    if not data.get("shipments"):
        if not force_api:
            return get_delivery_status(tracking_number, force_api=True)
        return {"Site": "UNKNOWN", "Tracking Number": tracking_number, "Status": "Unavailable", "Delivered On": "N/A", "ETA": "N/A"}

    shipment = data["shipments"][0]
    last_event = shipment.get("events", [])[0] if shipment.get("events") else {}
    status = last_event.get("statusCode", "N/A").capitalize()
    timestamp = last_event.get("timestamp", "")
    raw_location = last_event.get("location", {}).get("address", {}).get("addressLocality", "")
    eta = shipment.get("estimatedArrivalDate", "N/A")

    formatted_date = datetime.fromisoformat(timestamp).strftime('%d %B %Y') if timestamp else "N/A"
    site = location_to_site.get(raw_location.strip().upper(), "UNKNOWN")

    result = {
        "Site": site,
        "Tracking Number": tracking_number,
        "Status": status,
        "Delivered On": formatted_date,
        "ETA": eta if eta != "N/A" else "N/A"
    }
    cache[tracking_number] = result
    return result

def apply_filters():
    filtered_data = list(cache.values())
    for col, selected_values in filter_options.items():
        if selected_values:
            filtered_data = [r for r in filtered_data if r[col] in selected_values]
    return filtered_data

def process_tracking_numbers():
    raw_input = tracking_numbers_entry.get()
    if not raw_input:
        messagebox.showwarning("Input Required", "Please enter at least one tracking number.")
        return

    tracking_numbers = [x.strip() for x in raw_input.split(",") if x.strip()]
    for tn in tracking_numbers:
        get_delivery_status(tn)
        time.sleep(5)

    for row in treeview.get_children():
        treeview.delete(row)

    filtered_results = apply_filters()
    for r in filtered_results:
        treeview.insert("", "end", values=(r["Site"], r["Tracking Number"], r["Status"], r["Delivered On"], r["ETA"]))

def ask_download(data=None):
    if not data:
        data = list(cache.values())
    download = messagebox.askyesno("Download CSV", "Do you want to download the results as a CSV file?")
    if download:
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if path:
            df = pd.DataFrame(data)
            df.to_csv(path, index=False)
            messagebox.showinfo("Success", f"Results saved to {path}")

def load_cache():
    for row in cache_table.get_children():
        cache_table.delete(row)
    for result in cache.values():
        cache_table.insert("", "end", values=(result["Site"], result["Tracking Number"], result["Status"], result["Delivered On"], result["ETA"]))

def auto_refresh():
    if auto_refresh_enabled.get():
        try:
            interval = int(refresh_interval_entry.get())
            if interval > 0:
                process_tracking_numbers()
                window.after(interval * 1000, auto_refresh)
            else:
                messagebox.showwarning("Invalid Interval", "Please enter a positive number for the auto-refresh interval.")
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number for the auto-refresh interval.")

def clear_filters():
    for col in filter_options:
        filter_options[col] = []
    process_tracking_numbers()

auto_refresh()
window.mainloop()

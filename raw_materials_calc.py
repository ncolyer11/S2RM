import re
import os

import tkinter as tk

from tkinter import filedialog
from unicodedata import category as unicode_category

def clean_string(s):
    """Removes control characters, symbols, and trailing text."""
    return re.sub(r'[^a-zA-Z0-9\s].*', '', ''.join(c for c in s if unicode_category(c)[0] != 'C'))

def process_material_list(input_file):
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # (tail -n+6 | head -n-3)
    lines = lines[5:-3]

    # (cut -d'|' -f2,3)
    materials = {}
    for line in lines:
        parts = line.strip().split('|')
        if len(parts) > 2:
            material = parts[1].strip() # First part is just a blank before the first '|'
            quantity = parts[2].strip()

            cleaned_material = clean_string(material)
            materials[cleaned_material] = int(quantity)

    return materials

def get_litematica_dir():
    """Gets the Litematica directory, trying the S: drive first, then %appdata%."""
    s_drive_path = r"S:\mc\.minecraft\config\litematica"
    if os.path.exists(s_drive_path):
        return s_drive_path

    appdata_path = os.getenv('APPDATA')
    if appdata_path:
        appdata_litematica_path = os.path.join(appdata_path, ".minecraft", "config", "litematica")
        if os.path.exists(appdata_litematica_path):
            return appdata_litematica_path

    return None

def select_file():
    root = tk.Tk()
    root.withdraw()

    litematica_dir = get_litematica_dir()

    # Open choose file window in the Litematica directory
    if litematica_dir:
        file_path = filedialog.askopenfilename(
            initialdir=litematica_dir,
            title="Select material list file",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )
    else:
        file_path = filedialog.askopenfilename(
            initialdir=".",
            title="Select material list file",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )

    if file_path:
        materials_dict = process_material_list(file_path)
        print("Processed Materials Dictionary:")
        print(materials_dict)
    else:
        print("No file selected")

select_file()

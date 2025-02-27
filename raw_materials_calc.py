import tkinter as tk
from tkinter import filedialog
import re
import unicodedata
import os

def clean_string(s):
    """Removes control characters, symbols, and trailing text."""
    s = ''.join(c for c in s if unicodedata.category(c)[0] != 'C')
    s = re.sub(r'[^a-zA-Z0-9\s].*', '', s)
    return s

def process_material_list(input_file):
    # Step 1: Read the input file with UTF-8 encoding
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Step 2: Extract the relevant lines (tail -n+6 | head -n-3)
    lines = lines[5:-3]

    # Step 3: Clean up the lines and prepare data (cut -d'|' -f2,3)
    materials = {}
    for line in lines:
        # Remove leading/trailing whitespaces and split by '|'
        parts = line.strip().split('|')
        if len(parts) > 2:
            material = parts[1].strip() # First part is just a blank before the first '|'
            quantity = parts[2].strip()

            # Clean the material name
            cleaned_material = clean_string(material)

            # Convert quantity to an integer and store it in the dictionary
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
    # Step 4: Create a Tkinter root window and hide it
    root = tk.Tk()
    root.withdraw()

    # Get the Litematica directory
    litematica_dir = get_litematica_dir()

    # Step 5: Open file dialog in the Litematica directory
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
        # Step 6: Process the selected file
        materials_dict = process_material_list(file_path)
        print("Processed Materials Dictionary:")
        print(materials_dict)
    else:
        print("No file selected")

# Run the script
select_file()
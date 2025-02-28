import re
import os
import json
import math

import tkinter as tk

from tkinter import filedialog
from unicodedata import category as unicode_category

from constants import ITEM_TAGS

# TODO:
# - add a toggle for outputting in blocks vs ingots

def convert_name_to_tag(name):
    """Converts a name to a tag name."""
    name = clean_string(name).lower()
    
    # Replace spaces with underscores and remove trailing underscores
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+$', '', name)

    # 'Correcting' British to American spelling
    name = re.sub(r'chiselled_', 'chiseled_', name)
    name = re.sub(r'grey', 'gray', name)
    name = re.sub(r'dised', 'dized', name)

    # block_of_<name> -> <name>_block
    name = re.sub(r'block_of_(\w+)', r'\1_block', name)
    
    return ITEM_TAGS.get(name, name)

def clean_string(s):
    """Removes control characters, symbols, and trailing text."""
    return re.sub(r'[^a-zA-Z\'\s].*', '', ''.join(c for c in s if unicode_category(c)[0] != 'C'))

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

            # Remove weird characters and convert to item tag name
            cleaned_material = convert_name_to_tag(material)
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

    return file_path

def main():
    file_path = select_file()
    if file_path:
        materials_dict = process_material_list(file_path)
    else:
        print("No file selected")
        return
    
    with open("raw_materials_table.json", "r") as f:
        materials_table = json.load(f)
    
    total_materials = {}
    for material, quantity in materials_dict.items():
        if material in materials_table:
            for raw_material in materials_table[material]:
                rm_name, rm_quantity = raw_material["item"], raw_material["quantity"]
                rm_needed = rm_quantity * quantity
                total_materials[rm_name] = total_materials.get(rm_name, 0) + rm_needed
        else:
            raise ValueError(f"Material {material} not found in materials table.")

    # Ceil each quantity to the nearest int
    for material, quantity in total_materials.items():
        total_materials[material] = math.ceil(quantity)
        
    # Sort by highest quantity, then if equal quantity, sort by name
    total_materials = dict(sorted(total_materials.items(), key=lambda x: (-x[1], x[0])))

    with open("raw_materials.json", "w") as f:
        json.dump(total_materials, f, indent=4)


if __name__ == "__main__":
    main()

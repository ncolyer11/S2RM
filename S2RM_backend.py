import re
import os
import json
import math

import tkinter as tk

from tkinter import filedialog
from unicodedata import category as unicode_category

from constants import ITEM_TAGS, resource_path

def process_material_list(input_file: str) -> dict[str, int]:
    """
    Processes a Litematica material list file and returns a dictionary of materials and quantities.
    
    Parameters
    ----------
    input_file : str
        The path to the Litematica material list file.
    
    Returns
    -------
    dict[str, int]
        A dictionary of materials and quantities.
    
    Raises
    ------
    ValueError
        If the file is not a .txt or .csv Litematica material list.
    """
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Check if .txt or csv file
    if input_file.endswith('.txt'):
        return process_txt_material_list(lines)
    elif input_file.endswith('.csv'):
        return process_csv_material_list(lines)
    else:
        raise ValueError("File must be a .txt or .csv file.")

def process_txt_material_list(lines: list[str]) -> dict[str, int]:
    """Processes a .txt file and returns a dictionary of materials and quantities."""
    # Verify that the file is a Litematica material list by checking various formatting signals
    verify_txt_material_list(lines)

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

def process_csv_material_list(lines: list[str]) -> dict[str, int]:
    """Processes a .csv file and returns a dictionary of materials and quantities."""
    # Verify that the file is a Litematica material list by checking all the headers
    verify_csv_material_list(lines)
    materials = {}
    for line in lines[1:]:
        parts = line.strip().split('"')
        material = parts[1].strip()
        quantity = parts[2].split(',')[1].strip()

        # Remove weird characters and convert to item tag name
        cleaned_material = convert_name_to_tag(material)
        materials[cleaned_material] = int(quantity)
        
    return materials

def verify_txt_material_list(lines: list[str]) -> None:
    """Verifies that the file is a .txt Litematica material list."""
    if not lines or not lines[0].strip():
        raise ValueError("File is not a .txt Litematica material list. File is empty.")

    if not lines[0][:2] == '+-':
        raise ValueError(
            f"File is not a .txt Litematica material list. First line does not start with '+-'. "
            f"Found: {lines[0][:10]!r}"
        )

    if not re.match(r'\| (Material List for|Area Analysis for) ', lines[1]):
        raise ValueError(
            f"File is not a .txt Litematica material list. Second line does not start with "
            f"'| Material List for schematic '. Found: {lines[1][:30]!r}"
        )

    if not lines[-2].startswith('| Item '):
        raise ValueError(
            f"File is not a .txt Litematica material list. Second to last line does not start with "
            f"'| Item '. Found: {lines[-2][:20]!r}"
        )

    if 'Available' not in lines[-2]:
        raise ValueError(
            f"File is not a .txt Litematica material list. 'Available' not found in the second to "
            f"last line. Found: {lines[-2]!r}"
        )

    if not lines[-1][:2] == '+-':
        raise ValueError(
            f"File is not a .txt Litematica material list. Last line does not start with '+-'. "
            f"Found: {lines[-1][:10]!r}"
        )

def verify_csv_material_list(lines: list[str]) -> None:
    """Verifies that the file is a .csv Litematica material list."""
    csv_headers = lines[0].strip().split(',')
    if csv_headers != ['"Item"', '"Total"', '"Missing"', '"Available"']:
        raise ValueError(
            "File is not a .csv Litematica material list. Headers do not match expected format. "
            f"Found: {csv_headers}"
        )

    if not re.fullmatch(r'"[\w ]+"', lines[1].split(',')[0].strip()):
        raise ValueError(
            "File is not a .csv Litematica material list. First item is not \"alphabetic\". "
            f"Found: {lines[1].split(',')[0]!r}"
        )

    if not all(part.strip().isdigit() for part in lines[1].split(',')[1:4]):
        raise ValueError(
            f"File is not a .csv Litematica material list. Quantities are not all numeric. "
            f"Found: {lines[1].split(',')[1:4]}"
        )

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
    
    raw_mats_table_path = resource_path("data/raw_materials_table.json")
    with open(raw_mats_table_path, "r") as f:
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

    # Write to file
    with open("raw_materials.json", "w") as f:
        json.dump(total_materials, f, indent=4)

if __name__ == "__main__":
    main()

import re
import os
import json
import math

import tkinter as tk

from litemapy import Schematic
from tkinter import filedialog
from unicodedata import category as unicode_category

from constants import INVALID_BLOCKS, ITEM_TAGS, DF_STACK_SIZE, DF_SHULKER_BOX_STACK_SIZE, BLOCK_TAGS, SIMPLE_ENTITIES
from helpers import resource_path
from itertools import product

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

def process_litematic_file(input_file: str) -> dict[str, int]:
    """
    Processes a Litematica schematic file and returns a dictionary of materials and quantities.
    """
    schematic = Schematic.load(input_file)
    
    # print entities

    materials = {}
    regions = list(schematic.regions.values())
    # Handle schematics with multiple regions
    for region in regions:
        for x, y, z in product(region.xrange(), region.yrange(), region.zrange()):
            block = region[x, y, z]
            block_name = block.id.replace("minecraft:", "")
            if block_name in INVALID_BLOCKS:
                continue
            
            # Some blocks may break down into 2 items, e.g. a full cauldron or a candle cake
            item_names = convert_block_to_item(block_name)
            for item_name in item_names:
                materials[item_name] = materials.get(item_name, 0) + 1
    
        # Get materials required to craft/obtain entities
        for entity in region.entities:
            get_materials_from_entity(materials, entity)
    
        # Get items stored inside of inventories
        for tile_entity in region.tile_entities:
            get_materials_from_inventories(materials, tile_entity)

    # Ensure item names correspond to that in the materials table
    for material in list(materials.keys()):
        materials[convert_name_to_tag(material)] = materials.pop(material)

    # Return sorted materials by key
    return materials

def convert_block_to_item(block_name: str) -> str:
    block_name = re.sub(r'wall_hanging_', '', block_name)
    block_name = re.sub(r'wall_', '', block_name)
    block_name = re.sub(r'attached_', '', block_name)
    block_name = re.sub(r'potted_', '', block_name)
    
    block_name = BLOCK_TAGS.get(block_name, block_name)

    # Convert remove wall_ from things that go on walls like torches and signs
    if "candle" in block_name and "cake" in block_name:
        return ["candle", "cake"]
    elif match := re.match(r'(lava|water|powder_snow)_cauldron', block_name):
        return ["cauldron", f"{match.group(1)}_bucket"]
    elif match := re.match(r'(weeping|twisting)_vines_plant', block_name):
        return [f"{match.group(1)}_vines"]

    return [block_name] if isinstance(block_name, str) else block_name

def get_materials_from_entity(materials, entity):
    # if boat or minecart do some shi
    entity_name = entity.id.replace("minecraft:", "")
    if entity_name in SIMPLE_ENTITIES:
        materials[entity_name] = materials.get(entity_name, 0) + 1
    elif "boat" in entity_name or "minecart" in entity_name:
        materials[entity_name] = materials.get(entity_name, 0) + 1
    elif entity_name == "falling_block":
        block_name = entity.block_state.id.replace("minecraft:", "")
        if block_name in INVALID_BLOCKS:
            return
        item_names = convert_block_to_item(block_name)
        for item_name in item_names:
            materials[item_name] = materials.get(item_name, 0) + 1
    elif (spawn_egg_name := entity_has_spawn_egg(entity_name)):
        materials[spawn_egg_name] = materials.get(spawn_egg_name, 0) + 1
    elif "fish" in entity_name or entity_name in ["salmon", "cod", "axolotl", "tadpole"]:
        bucket_name = f"{entity_name}_bucket"
        materials[bucket_name] = materials.get(bucket_name, 0) + 1
    elif entity_name == "iron_golem":
        materials["iron_block"] = materials.get("iron_ingot", 0) + 4
        materials["carved_pumpkin"] = materials.get("carved_pumpkin", 0) + 1
    elif entity_name == "snow_golem":
        materials["snow_block"] = materials.get("snow_block", 0) + 1
        materials["carved_pumpkin"] = materials.get("carved_pumpkin", 0) + 1
    elif entity_name == "wither":
        materials["soul_sand"] = materials.get("soul_sand", 0) + 3
        materials["wither_skeleton_skull"] = materials.get("wither_skeleton_skull", 0) + 3
    elif entity_name == "ender_dragon":
        materials["end_crystal"] = materials.get("end_crystal", 0) + 1
    else:
        print(f"Adding entity without filtering: {entity_name}")
        materials[entity_name] = materials.get(entity_name, 0) + 1

def get_materials_from_inventories(materials, tile_entity):
    # if chest or barrel, iterate through all the items in its inventory and add to materials
    tile_entity_data = tile_entity.data
    if "Items" not in tile_entity_data:
        return
    
    items = tile_entity_data["Items"]
    for item in items:
        item_name = item["id"].replace("minecraft:", "")
        materials[item_name] = materials.get(item_name, 0) + item["Count"] 

def entity_has_spawn_egg(entity_name: str) -> str:
    # determine if an entity has a spawn egg, if so return it
    return ""

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

def condense_material(processed_materials: dict, material: str, quantity: float) -> None:
    if re.match(r'\w+_ingot$', material):
        block_name = material.replace("_ingot", "_block")
        add_resources(processed_materials, material, block_name, quantity)
    elif re.match(r'(diamond|redstone|coal|lapis_lazuli|emerald)$', material):
        block_name = f"{material}_block"
        add_resources(processed_materials, material, block_name, quantity)
    elif material == 'slime_ball':
        block_name = 'slime_block'
        add_resources(processed_materials, material, block_name, quantity)
    elif material == 'wheat':
        block_name = 'hay_block'
        add_resources(processed_materials, material, block_name, quantity)
    elif material == 'snowball':
        block_name = 'snow_block'
        add_resources(processed_materials, material, block_name, quantity, compact_num=4)
    elif material == 'bone_meal':
        block_name = 'bone_block'
        add_resources(processed_materials, material, block_name, quantity)
    elif material == "honey_bottle":
        block_name = "honey_block"
        add_resources(processed_materials, material, block_name, quantity, compact_num=4)
    else:
        processed_materials[material] = quantity

def add_resources(processed_materials: dict, material: str, block_name: str, quantity: float,
                  compact_num: int = 9) -> None:
    blocks_needed = int(quantity // compact_num)
    remaining_ingots = quantity - (blocks_needed * compact_num)

    if blocks_needed > 0:
        processed_materials[block_name] = processed_materials.get(block_name, 0) + blocks_needed
    if remaining_ingots > 0:
        processed_materials[material] = processed_materials.get(material, 0) + remaining_ingots
    
    if remaining_ingots > compact_num:
        raise ValueError(f"Error: {material} has more than {compact_num} remaining ingots.")

# XXX make work with var stack items
def process_exclude_string(input_string):
    """
    Processes the input string according to the given rules:

    1.  Extracts digits from the string.
    2.  Multiplies each digit by 64 if followed by 's', and by 64*27 if followed by 'sb'.
    3.  Calculates the sum of the multiplied digits.
    4.  Handles cases where the text following the digit is 's' or 'sb' (case-insensitive).

    Args:
        input_string: The input string to process.

    Returns:
        The sum of the multiplied digits.
    """

    if not input_string:
        return -1
    
    # Check if input matches the allowed characters pattern, not fully exhaustive e.g.
    # 'sb1' should be invalid but it isn't so don't go crazy with this
    if not re.fullmatch(r'(\d|\s|s|sb)+', input_string, re.IGNORECASE):
        return -1

    # Check for invalid combinations (e.g., 'ss', 'sss', etc.)
    if 'ss' in input_string or 'sss' in input_string:
        return -1
    
    total = 0
    matches = re.finditer(r"(\d+)(sb|s)?", input_string, re.IGNORECASE)

    for match in matches:
        digit = int(match.group(1))
        suffix = match.group(2)

        if suffix:
            if suffix.lower() == 's':
                total += digit * DF_STACK_SIZE
            elif suffix.lower() == 'sb':
                total += digit * DF_SHULKER_BOX_STACK_SIZE
        else:
            total += digit

    return total

def main():
    file_path = select_file()
    if file_path:
        materials_dict = process_material_list(file_path)
    else:
        print("No file selected")
        return
    
    raw_mats_table_path = resource_path("raw_materials_table.json")
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

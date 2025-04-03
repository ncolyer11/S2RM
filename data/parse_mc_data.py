import os
import re
import json
import shutil

from src.resource_path import resource_path
from src.constants import DATA_DIR, GAME_DATA_DIR, INVALID_BLOCKS, MC_DOWNLOADS_DIR
from src.S2RM_backend import block_to_item_name

def create_mc_data_dirs(mc_version: str):
    try:
        # Ensure 'data' directory exists
        os.makedirs(resource_path(DATA_DIR), exist_ok=True)
        
        # Then make the game data directory
        os.makedirs(resource_path(GAME_DATA_DIR), exist_ok=True)
        
        # Remove the old mc version directory if it exists
        version_dir = resource_path(os.path.join(GAME_DATA_DIR, mc_version))
        if os.path.exists(version_dir):
            shutil.rmtree(version_dir)
            print(f"Removed old directory: {version_dir} for {mc_version}")
        
        # Then make the new mc version directory
        os.makedirs(version_dir, exist_ok=False)
    except Exception as e:
        print(f"Error creating directories: {e}")

def parse_items_list():
    """
    Parse items from the downloaded item JSON files
    
    Returns:
        list: List of item names without .json extension
    """
    try:
        # Directory with item JSONs
        item_dir = resource_path(os.path.join(MC_DOWNLOADS_DIR, 'items'))
        
        # Get list of item names (filenames without .json)
        items = [
            os.path.splitext(filename)[0] for filename in os.listdir(item_dir) 
            if filename.endswith('.json')
        ]
        
        # Sort items by name
        items.sort()
        
        return items
    except Exception as e:
        print(f"Error parsing items list: {e}")
        return []

def parse_items_stack_sizes():
    """
    Parse items from `Items.java` that don't stack to 64, and their stack size (either 16 or 1)
    """
    # Current code for this, to run on mostly parsed data tho
    with open(resource_path(os.path.join(MC_DOWNLOADS_DIR, "Items.java")), "r") as f:
        lines = f.readlines()

    # Replace all newlines with nothing, and then replace all 'public static final Item ' with newlines
    lines = "".join(lines).replace("\n", "").replace("public static final Item ", "\n").split("\n")

    # Filter out lines that contain '.stacksTo(16)' or '.stacksTo(1)' or 'ToolMaterial' or
    # 'ArmorMaterial' or 'durability'
    pattern = re.compile(r'\.stacksTo\((16|1)\)|ToolMaterial|ArmorMaterial|durability')
    limited_stacked_lines = [line for line in lines if pattern.search(line)]

    limited_stack_items = {}
    for line in limited_stacked_lines:
        material = line.split(" ")[0].lower()
        quantity = 16 if "16" in line else 1
        limited_stack_items[material] = quantity

    # Sort the dictionary by key then quantity value
    return dict(sorted(limited_stack_items.items(), key=lambda x: (x[0], x[1])))

def parse_blocks_list():
    """Parses block names from Blocks.java, converting them into material names"""
    with open(resource_path(os.path.join(MC_DOWNLOADS_DIR, "Blocks.java")), "r") as f:
        lines = f.readlines()

    # Replace all newlines with nothing, and then replace all 'register(' with newlines
    lines = "".join(lines) \
        .replace("\n", "") \
        .replace("register(", "\n") \
        .replace("net.minecraft.references.Blocks.", '\n"') \
        .split("\n")

    item_names = [block_to_item_name(line.split(',')[0].strip()) for line in lines]

    # Remove unrelated lines in the code
    for i in range(len(item_names) - 1,  -1, -1):
        if not item_names[i].startswith('"'):
            item_names.pop(i)
        # Fix item name if it's semi-valid
        elif not item_names[i].endswith('"'):
            item_names[i] += '"'

    item_names.sort()

    # Remove duplicate entries after processing block names and sorting
    for i in range(len(item_names) - 1,  0, -1):
        if item_names[i].replace('"', '') in INVALID_BLOCKS or item_names[i] == item_names[i - 1]:
            item_names.pop(i)

    return item_names

def parse_entities_list():
    """Stub function for parsing entities from EntityType.java"""
    with open(resource_path(os.path.join(MC_DOWNLOADS_DIR, "EntityType.java")), "r") as f:
        lines = f.readlines()

    # Replace all newlines with nothing, and then replace all 'register(' with newlines
    lines = "".join(lines) \
        .replace("\n", "") \
        .replace("register(", "\n") \
        .split("\n")

    # XXX why is this using the block to item func for entities?
    entity_names = [block_to_item_name(line.split(',')[0].strip()) for line in lines]

    # Remove unrelated lines in the code
    for i in range(len(entity_names) - 1,  -1, -1):
        if not entity_names[i].startswith('"'):
            entity_names.pop(i)

    entity_names.sort()

    return entity_names

def save_json_file(mc_version, filename, data):
    """
    Save data to a JSON file in the GAME_DATA_DIR directory for a specific minecraft version
    
    Parameters
    ----------
    mc_version : str
        Minecraft version to save the data in a certain directory for
    filename : str
        Name of the output file
    data : list or dict
        Data to be saved as JSON
    """
    try:
        output_path = resource_path(os.path.join(GAME_DATA_DIR, mc_version, filename))
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Saved {filename}")
    except Exception as e:
        print(f"Error saving {filename}: {e}")

def cleanup_downloads():
    """
    Remove the minecraft_downloads directory
    """
    try:
        if os.path.exists(resource_path(MC_DOWNLOADS_DIR)):
            shutil.rmtree(resource_path(MC_DOWNLOADS_DIR))
            print("Cleaned up downloads directory")
    except Exception as e:
        print(f"Error cleaning up downloads: {e}")

if __name__ == '__main__':
    # items = parse_blocks_list()
    # for item in items:
    #     print(item)

    # entities = parse_entities_list()
    # for entity in entities:
    #     print(entity)

    ...
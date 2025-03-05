import os
import re
import json
import shutil

from helpers import resource_path

MC_DATA_PATH = resource_path("data/game")

def create_mc_data_dirs():
    try:
        # Ensure 'data' directory exists
        os.makedirs('data', exist_ok=True)
        
        # Then make the game data directory
        os.makedirs(MC_DATA_PATH, exist_ok=True)
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
        item_dir = 'minecraft_downloads/items'
        
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
    Stub function for parsing item stack sizes from Items.java
    
    TO BE IMPLEMENTED
    """
    print("parse_items_stack_sizes() stub - to be implemented")

    # Current code for this, to run on mostly parsed data tho
    # with open(resource_path("data/items.txt"), "r") as f:
    #     lines = f.readlines()

    # pattern = re.compile(r'\.stacksTo\((16|1)\)|ToolMaterial|ArmorMaterial|durability')
    # limited_stacked_lines = [line for line in lines if pattern.search(line)]

    # limited_stack_items = {}
    # for line in limited_stacked_lines:
    #     material = line.split(" ")[0].lower()
    #     quantity = 16 if "16" in line else 1
    #     limited_stack_items[material] = quantity

    # # Sort the dictionary by key then quantity value
    # sorted_limited_stack_items = dict(sorted(limited_stack_items.items(), key=lambda x: (x[0], x[1])))

    # with open(resource_path("limited_stacks.json"), "w") as f:
    #     json.dump(sorted_limited_stack_items, f, indent=4)

    return {}

def parse_blocks_list():
    """
    Stub function for parsing blocks from Blocks.java
    
    TO BE IMPLEMENTED
    """
    print("parse_blocks_list() stub - to be implemented")
    return []

def parse_entities_list():
    """
    Stub function for parsing entities from EntityType.java
    
    TO BE IMPLEMENTED
    """
    print("parse_entities_list() stub - to be implemented")
    return []

def save_json_file(filename, data):
    """
    Save data to a JSON file in the MC_DATA_PATH directory
    
    Parameters
    ----------
    filename : str
        Name of the output file
    data : list or dict
        Data to be saved as JSON
    """
    try:
        output_path = os.path.join(MC_DATA_PATH, filename)
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
        if os.path.exists('minecraft_downloads'):
            shutil.rmtree('minecraft_downloads')
            print("Cleaned up downloads directory")
    except Exception as e:
        print(f"Error cleaning up downloads: {e}")

def main():
    # Create the 'data/game' directories
    create_mc_data_dirs()
    
    # Parse and save items list
    items_list = parse_items_list()
    save_json_file('items.json', items_list)
    
    # Parse and save entities list (stub)
    entities_list = parse_entities_list()
    save_json_file('entities.json', entities_list)
    
    # Parse and save blocks list (stub)
    blocks_list = parse_blocks_list()
    save_json_file('blocks.json', blocks_list)
    
    # Parse item stack sizes (stub)
    items_stack_sizes = parse_items_stack_sizes()
    save_json_file('limited_stack_items.json', items_stack_sizes)
    
    # Clean up downloads directory
    cleanup_downloads()

if __name__ == '__main__':
    main()
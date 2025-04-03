import json
import re
import os

from itertools import product
from litemapy import Schematic, Entity, TileEntity
from unicodedata import category as unicode_category

from src.constants import CONDENSABLES, GOLEM_RECIPES, HEADGEAR_KWS, INVALID_BLOCKS, \
    INVALID_ENTITIES, ITEM_TAGS, DF_STACK_SIZE, BLOCK_TAGS, SIMPLE_ENTITIES, SHULKER_BOX_SIZE
from src.helpers import add_material, int_to_roman, get_limit_stack_items, \
    print_formatted_entity_data

def input_file_to_mats_dict(input_file: str) -> dict[str, int]:
    """
    Processes a Litematica material list file and returns a dictionary of materials and quantities.
    
    Parameters
    ----------
    input_file : str
        The path to the Litematica material list file, either .litematic, .txt, or .csv.
    
    Returns
    -------
    dict[str, int]
        A dictionary of materials and quantities.
    
    Raises
    ------
    ValueError
        If the file is not a .txt or .csv Litematica material list.
    """
    is_schem = input_file.endswith('.litematic')
    if not is_schem and os.path.exists(input_file):
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

    # Check if .txt or csv file
    if is_schem:
        return process_litematic_file(input_file)
    elif input_file.endswith('.txt'):
        return process_txt_material_list(lines)
    elif input_file.endswith('.csv'):
        return process_csv_material_list(lines)
    else:
        raise ValueError("File must be a .txt or .csv file.")

def get_litematica_dir():
    """
    Gets the Litematica directory, checking for S2RM specific directories first, and then the default.
    """
    if appdata_path := os.getenv('APPDATA'):
        appdata_litematica_path = os.path.join(appdata_path, ".minecraft", "schematics")
        for dir_name in os.listdir(appdata_litematica_path):
            if "s2rm" in dir_name.lower():
                return os.path.join(appdata_litematica_path, dir_name)

        if os.path.exists(appdata_litematica_path):
            return appdata_litematica_path

    return "" # Return an empty string if directory not found

def process_exclude_string(input_str: str, material: str) -> int:
    """
    Processes the input string according to the given rules:

    1.  Extracts digits from the string.
    2.  Multiplies each digit by 1/16/64 if followed by 's', and by 64*27 if followed by 'sb'.
    3.  Calculates the sum of the multiplied digits.
    4.  Handles cases where the text following the digit is 's' or 'sb' (case-insensitive).

    Parameters:
    ----------
    input_str : str
        The input string to process.
    material : str
        The name of the material, required to get the stack size.

    Returns:
        The sum of the multiplied digits, or -1 if the input is invalid.
    """
    # Check if input is empty
    if not input_str:
        return -1
    
    # Check if input matches the allowed characters pattern, not fully exhaustive e.g.
    # 'sb1' should be invalid but it isn't so don't go crazy with this
    if not re.fullmatch(r'(\d|\s|s|sb)+', input_str, re.IGNORECASE):
        return -1

    # Check for invalid combinations (e.g., 'ss', 'sss', etc.)
    if 'ss' in input_str or 'sss' in input_str:
        return -1
    
    matches = re.finditer(r"(\d+)(sb|s)?", input_str, re.IGNORECASE)

    LIMITED_STACK_ITEMS = get_limit_stack_items() # XXX opening this file every time is inefficient
    stack_size = LIMITED_STACK_ITEMS.get(material, DF_STACK_SIZE)
    shulker_stack_size = stack_size * SHULKER_BOX_SIZE
    total = 0
    for match in matches:
        digit = int(match.group(1))
        suffix = match.group(2)

        if suffix:
            if suffix.lower() == 's':
                total += digit * stack_size
            elif suffix.lower() == 'sb':
                total += digit * shulker_stack_size
        else:
            total += digit

    return total

def condense_material(processed_materials: dict, material: str, quantity: float) -> None:
    if re.match(r'\w+_ingot$', material):
        block_name = material.replace("_ingot", "_block")
        add_resources(processed_materials, material, block_name, quantity)
    elif material in CONDENSABLES:
        block_name, compact_num = CONDENSABLES[material]
        add_resources(processed_materials, material, block_name, quantity, compact_num)
    else:
        processed_materials[material] = quantity

#############################################
################## HELPERS ##################
#############################################

def add_resources(materials: dict, material: str, block_name: str, quantity: float,
                  compact_num: int = 9):
    """Adds a compacted resource, both its block form and remaining resources, to a materials dict."""
    blocks_needed = int(quantity // compact_num)
    remaining_ingots = quantity - (blocks_needed * compact_num)

    if blocks_needed > 0:
        materials[block_name] = materials.get(block_name, 0) + blocks_needed
    
    if remaining_ingots > 0:
        materials[material] = materials.get(material, 0) + remaining_ingots
    
    if remaining_ingots > compact_num:
        raise ValueError(f"Error: {material} has more than {compact_num} remaining ingots.")

def convert_name_to_tag(name):
    """
    Converts a name (name a user sees) to a tag name (what the game internally uses).
    
    Handles translations for most english languages, and cleaning for invalid item names.
    
    These alternate languages and modified item names come from a user's language settings and
    any resources they may have set that change item names.
     - e.g. adding tick delay info to redstone component names (can sometimes include unicode too).
    """
    # Stage 1: Initial cleaning (keep numbers for special cases)
    name = clean_string_stage1(name).lower()

    # Handle special cases where the item name is meant to have a number in it, e.g., for music discs,
    # or if an item has been marked as an unfiltered, but still valid, entity not in raw_materials_table.json
    if re.match(r'(music_disc_\d+|disc_fragment_\d+|block36|\$.*)$', name):
        return name

    # Stage 2: Further cleaning (remove numbers and other unnecessary characters)
    name = clean_string_stage2(name)

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

def convert_block_to_item(block_name: str) -> str:
    """
    Uses a raw block name used by the game, finds its equivalent item name, and returns it as a list
    of item names.
    
    A list is used as some blocks can break down into multiple items, e.g. a candle cake.
    """
    block_name = block_to_item_name(block_name)

    # Handle 1 block -> 2 items edge cases
    if "candle" in block_name and "cake" in block_name:
        return ["candle", "cake"]
    elif match := re.match(r'(lava|water|powder_snow)_cauldron', block_name):
        return ["cauldron", f"{match.group(1)}_bucket"]

    return [block_name] if isinstance(block_name, str) else block_name

def block_to_item_name(block_name: str) -> str:
    """
    Takes a block name used by the game, and converts it to the internal name used for its item.
    
    Returns the processed block name (likely to also be its item name) if no item name is found
    in BLOCK_TAGS.
    """
    is_quoted = block_name.startswith('"')
    data_name = block_name.lower().replace('"', '')

    data_name = re.sub(r'wall_', '', data_name)
    data_name = re.sub(r'attached_', '', data_name)
    data_name = re.sub(r'potted_', '', data_name)
    
    data_name = BLOCK_TAGS.get(data_name, data_name)

    if match := re.match(r'(weeping|twisting)_vines_plant', data_name):
        data_name = f"{match.group(1)}_vines"

    item_name = f'"{data_name}"' if is_quoted else data_name
    return item_name

def clean_string_stage1(s):
    """Removes control characters and symbols but keeps numbers."""
    return re.sub(r'[^[a-zA-Z0-9_\s\'].*', '', ''.join(c for c in s if unicode_category(c)[0] != 'C'))

def clean_string_stage2(s):
    """Removes numbers and trailing text."""
    return re.sub(r'[^[a-zA-Z_\s\'].*', '', ''.join(c for c in s if unicode_category(c)[0] != 'C' and not c.isdigit()))

### ENTITY HANDLING IN SCHEMATICS ###

def get_materials_from_entity(materials: dict[str, int], entity: Entity):
    """Extracts materials required for an entity in a structured way."""
    name = entity.id.replace("minecraft:", "")
    data = entity.data

    extract_entity_materials(materials, name, data)
    handle_additional_entity_materials(materials, data)

def get_materials_from_inventories(materials: dict[str, int], tile_entity: TileEntity):
    """Extracts materials from inventories by checking their NBT."""
    data = tile_entity.data
    items = []
    if "Items" in data:
        items = data["Items"]
    elif "Item" in data:
        items = [data["Item"]]

    for item in items:
        item_name = item["id"].replace("minecraft:", "")
        count = item.get("count", item.get("Count", 0)) # Fallback to 0 if neither key exists
        add_material(materials, item_name, count)

def extract_entity_materials(materials: dict[str, int], entity_name, data):
    # Direct simple entities
    if entity_name in SIMPLE_ENTITIES:
        add_material(materials, entity_name)

    # Item frames
    elif "item_frame" in entity_name:
        add_material(materials, entity_name)
        if "Item" in data:
            add_material(materials, data['Item']['id'].replace("minecraft:", ""))

    # Boats and minecarts (check for extra items inside)
    elif "boat" in entity_name or "minecart" in entity_name:
        # Convert generic boat name to specific boat name including the wood type
        if "Type" in data:
            entity_name = f"{data['Type']}_boat"
        add_material(materials, entity_name)
        for item in data.get("Items", []):
            if "count" in item:
                add_material(materials, item["id"].replace("minecraft:", ""), item["count"])
            else:
                add_material(materials, item["id"].replace("minecraft:", ""), item["Count"])

    # Falling blocks
    elif entity_name == "falling_block":
        block_name = data['BlockState']['Name'].replace("minecraft:", "")
        if block_name not in INVALID_BLOCKS:
            for item_name in convert_block_to_item(block_name):
                add_material(materials, item_name)

    # Bucket-able entities
    elif entity_name in {"salmon", "cod", "axolotl", "tadpole"} or "fish" in entity_name:
        add_material(materials, f"{entity_name}_bucket")

    # "Craftable" golem-like entities
    elif entity_name in GOLEM_RECIPES:
        for item, count in GOLEM_RECIPES[entity_name].items():
            add_material(materials, item, count)

    # Ender Dragon special case ofc
    elif entity_name == "ender_dragon":
        if "DragonPhase" in data:
            add_material(materials, "end_crystal", 4)

    # Leftover, but still not invalid, entities
    elif entity_name not in INVALID_ENTITIES:
        print(f"Adding entity without filtering: {entity_name}")
        # Encode the entity_name with a $ to mark it as valid despite not being in raw_materials_table.json
        add_material(materials, f"${entity_name}")

    # Invalid entities, e.g. item (entity)
    else:
        print(f"Skipping invalid entity: {entity_name}")

def handle_additional_entity_materials(materials: dict[str, int], data):
    # Leash check
    if "leash" in data:
        add_material(materials, "lead")
        
    # Check useful, and hence intentionally part of the schematic, enchants on gear
    if "ArmorItems" in data:
        for item in data.get("ArmorItems", []):
            item_name = item.get("id", "").replace("minecraft:", "")
            
            # And any headgear regardless of enchantments
            if any(keyword in item_name for keyword in HEADGEAR_KWS):
                add_material(materials, item_name)
            
            # Then check for specific, useful enchantments on certain types of gear

            # Frosted ice generation using armour stands e.g.
            process_enchanted_item(materials, item, "boots", {"frost_walker": 2})
            # Giving an entity less drag in water e.g.
            process_enchanted_item(materials, item, "boots", {"depth_strider": 3})
    
    # Also check for useful enchantments on certain types of weapons/tools
    if "HandItems" in data:
        for item in data.get("HandItems", []):
            item_name = item.get("id", "").replace("minecraft:", "")
            
            # TNT Looting e.g.
            process_enchanted_item(materials, item, "sword", {"looting": 3})
            # Efficient villager conversion
            process_enchanted_item(materials, item, "sword", {"sharpness": 5})
            process_enchanted_item(materials, item, "axe", {"sharpness": 5})

def process_enchanted_item(materials: dict[str, int], item, gear, enchantment: dict[str, int]):
    # Skip processing if item doesn't exist or doesn't match gear type
    item_name = item.get("id", "").replace("minecraft:", "")
    if not item_name or gear not in item_name:
        return
    
    # Cooked access to list of enchantments field
    enchantments = item.get("components", {}).get("minecraft:enchantments", {})
    enchantments = {k.replace('minecraft:', ''): int(v) for k, v in enchantments.get("levels", {}).items()}
    
    # Check if the gear is the correct type and the enchantment (including its level) is present
    for enchant_name, enchant_level in enchantment.items():
        if enchant_name in enchantments and enchantments[enchant_name] >= enchant_level:
            # Add the enchanted book to materials
            level_in_roman = int_to_roman(enchantments[enchant_name])
            add_material(materials, f"${enchant_name}_{level_in_roman}_book")
            
            # If the base gear hasn't been added yet, add it
            if item_name not in materials:
                add_material(materials, item_name)

#######################################################
################## FILE MANAGEMENT ####################
#######################################################

def process_litematic_file(input_file: str) -> dict[str, int]:
    """
    Processes a Litematica schematic file and returns a dictionary of materials and quantities.
    
    Raises
    ------
    CorruptedSchematicError:
        if the schematic file is malformed in any way
    """
    # This will raise an error if the file is not a valid Litematica file
    schematic = Schematic.load(input_file)
    
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
            # print_formatted_entity_data(entity.data)
            get_materials_from_entity(materials, entity)
        
        # Get items stored inside of inventories
        for tile_entity in region.tile_entities:
            get_materials_from_inventories(materials, tile_entity)
            
    # Ensure item names correspond to that in the materials table
    for material in list(materials.keys()):
        materials[convert_name_to_tag(material)] = materials.pop(material)

    return materials

def process_txt_material_list(lines: list[str]) -> dict[str, int]:
    """
    Processes a .txt file and returns a dictionary of materials and quantities.
    
    Raises
    ------
    ValueError:
        if the file is not a valid Litematica materials.txt list
    """
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

def process_csv_material_list(lines: list[str]) -> dict[str, int]:
    """
    Processes a .csv file and returns a dictionary of materials and quantities.
    
    Raises
    ------
    ValueError:
        if the file is not a valid Litematica materials.csv list
    """
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

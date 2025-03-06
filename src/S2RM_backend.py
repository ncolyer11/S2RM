import re
import os

from itertools import product
from litemapy import Schematic, Entity, TileEntity
from unicodedata import category as unicode_category

from src.constants import GOLEM_RECIPES, HEADGEAR_KWS, INVALID_BLOCKS, INVALID_ENTITIES, ITEM_TAGS, DF_STACK_SIZE, BLOCK_TAGS, \
    SIMPLE_ENTITIES, LIMITED_STACK_ITEMS, SHULKER_BOX_SIZE
from src.helpers import add_material, int_to_roman, print_formatted_entity_data


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

def process_txt_material_list(lines: list[str]) -> dict[str, int]:
    """Processes a .txt file and returns a dictionary of materials and quantities."""
    # Verify that the file is a Litematica material list by checking various formatting signals
    try:
        verify_txt_material_list(lines)
    except ValueError as e:
        print(e)
        return None

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
    try:
        verify_csv_material_list(lines)
    except ValueError as e:
        print(e)
        return None

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

def convert_block_to_item(block_name: str) -> str:
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

def get_materials_from_entity(materials: dict[str, int], entity: Entity):
    """Extracts materials required for an entity in a structured way."""
    data = entity.data
    entity_name = entity.id.replace("minecraft:", "")

    extract_entity_materials(materials, entity_name, data)
    handle_additional_entity_materials(materials, data)

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
            added = False
            # Frosted ice generation using armour stands e.g.
            added = process_enchanted_item(materials, item, "boots", {"frost_walker": 2}, added)
            # Giving an entity less drag in water e.g.
            added = process_enchanted_item(materials, item, "boots", {"depth_strider": 3}, added)
    
    # Also check for useful enchantments on certain types of weapons/tools
    if "HandItems" in data:
        for item in data.get("HandItems", []):
            item_name = item.get("id", "").replace("minecraft:", "")
            
            added = False
            # TNT Looting e.g.
            added = process_enchanted_item(materials, item, "sword", {"looting": 3}, added)
            # Efficient villager conversion
            added = process_enchanted_item(materials, item, "sword", {"sharpness": 5}, added)
            added = process_enchanted_item(materials, item, "axe", {"sharpness": 5}, added)

def process_enchanted_item(materials: dict[str, int], item, gear, enchantment: dict[str, int], item_added):
    # Cooked access to list of enchantments field
    enchantments = item.get("components", {}).get("minecraft:enchantments", {})
    enchantments = {k.replace('minecraft:', ''): int(v) for k, v in enchantments.get("levels", {}).items()}
    
    item_name = item.get("id", "").replace("minecraft:", "")
    
    # Check if the gear is the correct type and the enchantment (including its level) is present
    if gear in item_name:
        # Check if the enchantment is present and at the correct level
        for enchant_name, enchant_level in enchantment.items():
            if enchant_name in enchantments and enchantments[enchant_name] >= enchant_level:
                # Add the enchanted book to materials
                level_in_roman = int_to_roman(enchantments[enchant_name])
                add_material(materials, f"${enchant_name}_{level_in_roman}_book")
                
                # If the base gear hasn't been added yet, add it
                if not item_added:
                    add_material(materials, item_name)
                    return True
        
    return False

def get_materials_from_inventories(materials: dict[str, int], tile_entity: TileEntity):
    """Extracts materials from inventories by checking their NBT."""
    data = tile_entity.data
    if "Items" in data:
        items = data["Items"]
    elif "Item" in data:
        items = [data["Item"]]
    else:
        return

    for item in items:
        item_name = item["id"].replace("minecraft:", "")

        if "count" in item:
            add_material(materials, item_name, item["count"])
        else:
            add_material(materials, item_name, item["Count"])

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
    # Handle special cases where the item name is meant to have a number in it, e.g. for music discs,
    # or if an item has been marked as an unfiltered, but still valid, entity not in raw_materials_table.json
    if re.match(r'(music_disc_\d+|disc_fragment_\d+|block36|\$.*)$', name):
        return name
    
    # Remove control characters, symbols, and trailing text from the name
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
    return re.sub(r'[^[a-zA-Z_\s\'].*', '', ''.join(c for c in s if unicode_category(c)[0] != 'C'))

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

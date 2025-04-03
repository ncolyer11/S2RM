"""Functions for handling entities and tile entities in Minecraft schematics."""

from litemapy import Entity, TileEntity

from src.helpers import add_material, convert_block_to_item, int_to_roman
from src.constants import GOLEM_RECIPES, HEADGEAR_KWS, INVALID_BLOCKS, INVALID_ENTITIES, \
    SIMPLE_ENTITIES

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

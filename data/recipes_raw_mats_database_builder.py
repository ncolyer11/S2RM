import os
import re
import json

import networkx as nx

from tqdm import tqdm
from collections import defaultdict

from src.resource_path import resource_path
from src.helpers import convert_block_to_item
from data.graph_recipes import build_crafting_graph
from src.constants import BLOCKS_JSON, GAME_DATA_DIR, IGNORE_ITEMS_REGEX, AXIOM_MATERIALS_REGEX, \
    ITEMS_JSON, MC_DOWNLOADS_DIR, PRIORITY_CRAFTING_METHODS, TAGGED_MATERIALS_BASE

def main():
    recipe_json_raw_data = get_recipe_data_from_json()
    raw_materials_cost = get_raw_materials_cost_dict(recipe_json_raw_data)
        
    recipe_graph = build_crafting_graph(raw_materials_cost)
    generate_master_raw_mats_list(recipe_graph)
    
    # list_crafting_recipes(recipe_graph, 'chiseled_resin_bricks')
    # display_graph_sample(recipe_graph, 'chiseled_resin_bricks', depth=7)
    # display_graph_sample(recipe_graph, 'all', depth=500)

######################
### RECIPE RELATED ###
######################
def get_raw_materials_cost_dict(recipe_json_raw_data: dict) -> dict:
    raw_materials_cost = {}
    
    for item_name, recipe in recipe_json_raw_data.items():
        craft_type = recipe['type'].replace('minecraft:', '')
        if re.match(IGNORE_ITEMS_REGEX, item_name):
            continue

        # Return a dictionary of material types and their required quantity
        if (items := get_items_from_craft_type(recipe, craft_type)) is None:
            continue

        # Remove text after & incl '_from' to ignore alternate methods and 'dye_' from wool recipes
        item_name = item_name.split('_from')[0]
        item_name = re.sub(r'^dye_', '', item_name)
        item_name = re.sub(r'_smithing$', '', item_name)
        
        modified_items = {}
        for ingredient, count in items.items():
            # Change the name of a hashed material inside items to its base material name
            if ingredient.startswith('#'):
                base_material = TAGGED_MATERIALS_BASE[ingredient]
                modified_items[base_material] = count
            else:
                modified_items[ingredient] = count

        if item_name not in raw_materials_cost:
            raw_materials_cost[item_name] = modified_items
        # Only overwrite if shaped or shapeless method
        elif craft_type in PRIORITY_CRAFTING_METHODS and item_name != 'stick':
            raw_materials_cost[item_name] = modified_items
    
    return raw_materials_cost

def get_items_from_craft_type(recipe: dict, craft_type: str) -> dict[str, int]:
    group = recipe.get('group', None)
    if group is not None and group == 'wool':
        craft_type = 'dye_wool'

    match craft_type:
        case 'crafting_shaped':
            return get_shaped_ingredients(recipe)
        case 'crafting_shapeless':
            return get_shapeless_ingredients(recipe)
        # Smelting recipes only have one ingredient and always of quantity 1
        case 'smelting':
            return get_smelting_ingredients(recipe)
        # Handle smithing recipes for netherite gear
        case 'smithing_transform':
            base_material = recipe['addition'].replace('minecraft:', '')
            base_item = recipe['base'].replace('minecraft:', '')
            template = recipe['template'].replace('minecraft:', '')
            return {base_material: 1.0, base_item: 1.0, template: 1.0, 'count': 1.0}
        # Only 'crafting_transmute' recipes are bundles (which are ignored items) and shulker boxes
        case 'crafting_transmute':
            dye = recipe['material'].replace('minecraft:', '')
            return {'shulker_box': 1.0, dye: 1.0, 'count': 1.0}
        case 'dye_wool':
            if (dye := recipe['ingredients'][0].replace('minecraft:', '')) == 'white_dye':
                return {'white_wool': 1.0, 'count': 1.0}
            else:
                return {'white_wool': 1.0, dye: 1.0, 'count': 1.0}
        case _:
            return None

def get_shaped_ingredients(recipe) -> dict[str, int]:
    ingredients = {}
    item_keys = recipe['key']
    pattern = ''.join(recipe['pattern']).replace(' ', '')

    for key in pattern:
        item = item_keys[key]
        add_ingredient(ingredients, item)
    ingredients['count'] = recipe['result']['count']
    return ingredients

def get_shapeless_ingredients(recipe) -> dict[str, int]:
    ingredients = {}
    for item in recipe['ingredients']:
        add_ingredient(ingredients, item)

    ingredients['count'] = recipe['result']['count']
    return ingredients

def get_smelting_ingredients(recipe) -> dict[str, int]:
    ingredients = {}
    item = recipe['ingredient']
    add_ingredient(ingredients, item)
    
    ingredients['count'] = 1.0
    return ingredients

###############
### HELPERS ###
###############
def get_recipe_data_from_json(recipe_path: str) -> dict:
    """Recipe path should contain all the .json recipes when you download the game files."""
    recipe_json_raw_data = {}
    recipe_path = resource_path(recipe_path)
    # Loop through every recipe.json file
    file_list = [f for f in os.listdir(recipe_path) if f.endswith('.json')]
    total_files = len(file_list)

    for filename in tqdm(file_list, total=total_files, desc="Processing files"):
        file_path = os.path.join(recipe_path, filename)
        item_name = filename.split('.')[0]
        
        # Load json into the dict
        with open(file_path, 'r') as file:
            item_recipe_data = json.load(file)
            recipe_json_raw_data[item_name] = item_recipe_data

    return recipe_json_raw_data

def add_ingredient(ingredients: dict[str, dict], item: str):
    # If their are multiple items available, take the shortest name one (most likely to be a raw material)
    item = (item if not isinstance(item, list) else min(item, key=len)).replace('minecraft:', '')
    ingredients[item] = ingredients.setdefault(item, 0) + 1.0

#####################################
### RAW MATERIALS LIST GENERATION ###
#####################################
def generate_raw_materials_table_dict(
    version: str,
    *,
    items_list: list[str],
    blocks_list: list[str],
) -> dict[str, list[dict[str, float]]]:
    """
    Top-level function for generating a versions raw materials table for every crafting recipe.
    
    This includes 'crafting recipes' for entities, and blocks without typical crafting recipes,
    e.g. concrete, chipped anvils.
    """
    recipe_path = resource_path(os.path.join(MC_DOWNLOADS_DIR, 'recipe'))
    recipe_json_raw_data = get_recipe_data_from_json(recipe_path)
    raw_materials_cost = get_raw_materials_cost_dict(recipe_json_raw_data)
        
    recipe_graph = build_crafting_graph(raw_materials_cost)
    raw_materials_dict = generate_master_raw_mats_list(recipe_graph, items_list)
    calculate_block_ingredients(
        recipe_graph,
        raw_materials_dict,
        items_list,
        blocks_list,
        version,
    ) 
    # calculate_entity_ingredients(recipe_graph, raw_materials_dict, version)
    
    # Preserve legacy "chain" identifier now that Mojang renamed the recipe to "iron_chain".
    if "iron_chain" in raw_materials_dict and "chain" not in raw_materials_dict:
        raw_materials_dict["chain"] = [dict(entry) for entry in raw_materials_dict["iron_chain"]]

    # Ensure the raw materials list is sorted alphabetically by item name
    return dict(sorted(raw_materials_dict.items()))

def generate_master_raw_mats_list(
    recipe_graph: nx.DiGraph, items_list: list[str]
) -> dict[str, list[dict[str, float]]]:
    """Generates a master list of all items and their raw materials."""
    # Open data/items.json and get items field
    master_items_list = sorted(items_list)

    master_raw_mats_list = {}
    for item in master_items_list:
        master_raw_mats_list[item] = get_ingredients(recipe_graph, item)

    return master_raw_mats_list

def calculate_block_ingredients(
    recipe_graph: nx.DiGraph,
    raw_materials_dict: dict[str, list[dict[str, float]]],
    items_list: list[str],
    blocks_list: list[str],
    version: str,
):
    """Calculates the raw materials for blocks, breaking down blocks such as concrete, etc."""
    items_list = sorted(items_list)
    blocks_list = sorted(blocks_list)

    # Get the list of blocks that aren't in items_list
    blocks_list = [block for block in blocks_list if block not in items_list]

    for block in blocks_list:
        block_ingredients = []
        
        # Deconstruct the block into 1 or more items (e.g. a candle cake -> candle + cake)
        items = convert_block_to_item(block)
        for item in items:
            block_ingredients.extend(get_ingredients(recipe_graph, item))
        
        # Combine individual item ingredient dictions into a single one
        block_ingredients_dict = {}
        for ingredient in block_ingredients:
            item, quantity = ingredient["item"], ingredient["quantity"]
            block_ingredients_dict[item] = block_ingredients_dict.get(item, 0) + quantity

        # Sort the ingredients by quantity (descending), then by name
        raw_materials_dict[block] = sorted(
            [{"item": item, "quantity": quantity} for item, quantity in block_ingredients_dict.items()],
            key=lambda x: (-x["quantity"], x["item"])
        )
            
def calculate_entity_ingredients(recipe_graph: nx.DiGraph, 
                                 raw_materials_dict: dict[str, list[dict[str, float]]], version: str):
    """Calculates the raw materials for entities, breaking down entities such as carts, golems, etc."""
    # NOTE Entities actually do need to be processed each time as they can have
    # varying nbt and so won't just have a base 'recipe' each time
    
    # entities_path = resource_path(os.path.join(GAME_DATA_DIR, version, ENTITIES_JSON))
    # with open(entities_path, 'r') as f:
    #     entities_list = sorted(json.load(f))
        
def get_ingredients(recipe_graph: nx.DiGraph, target_item: str) -> list[dict[str, float]]:
    """Lists all raw materials needed to craft a target item, handling circular dependencies."""
    # Convert 'uncraftable' (created outside a crafting table) to their raw base material
    target_item = re.sub(r'^(chipped|damaged)_anvil$', 'anvil', target_item)
    target_item = re.sub(r'(\w+)_concrete$', r'\1_concrete_powder', target_item)
    target_item = re.sub(r'(exposed|weathered|oxidized)_', '', target_item)
    if target_item in ['waxed_copper', 'copper']:
        target_item += '_block'

    # Return single item if it doesn't have a crafting recipe
    if target_item not in recipe_graph:
        return [{"item": target_item, "quantity": 1.0}]

    raw_materials = defaultdict(float)
    _get_ingredients_recursive(recipe_graph, target_item, raw_materials)

    # Convert to sorted list, highest quantity first, then by item name alphabetically
    return sorted(
        [{"item": item, "quantity": quantity} for item, quantity in raw_materials.items()],
        key=lambda x: (-x["quantity"], x["item"])
    )

def _get_ingredients_recursive(graph: nx.DiGraph, target_item: str, raw_materials: dict, quantity=1.0):
    """Recursive helper function to find raw materials, handling circular dependencies."""
    # For handling edge cases where items don't abide by the rules (e.g. netherite, hanging signs, etc)
    if _handle_special_cases(graph, target_item, raw_materials, quantity):
        return
    
    # Cycle detected when 2 semi-raw materials craft into each other
    if re.match(AXIOM_MATERIALS_REGEX, target_item, re.VERBOSE):
        raw_materials[target_item] += quantity
        # Ensure other, non-axiomatic ingredients are accounted for when handling smithing templates
        _handle_smithing_template(graph, target_item, raw_materials, quantity)
        return

    # Base case: no ingredients, it's a raw material
    if not (ingredients := list(graph.predecessors(target_item))):
        raw_materials[target_item] += quantity
        return

    # If the item does have ingredients, find the ingredients for each of those ingredients, and so on
    for ingredient in ingredients:
        weight = graph[ingredient][target_item]['weight']
        _get_ingredients_recursive(graph, ingredient, raw_materials, quantity * weight)

def _handle_special_cases(graph: nx.DiGraph, target_item: str, raw_materials: dict, quantity: int) -> bool:
    # Special case for when an ingot, netherite, isn't actually the raw material
    if target_item == 'netherite_ingot':
        _get_ingredients_recursive(graph, 'netherite_scrap', raw_materials, 4.0 * quantity)
        _get_ingredients_recursive(graph, 'gold_ingot', raw_materials, 4.0 * quantity)
        return True

    # Can't have users thinking they need a shit-ton of honey now do we
    if target_item == 'sugar':
        _get_ingredients_recursive(graph, 'sugar_cane', raw_materials, 1.0 * quantity)
        return True
    
    # Another case for an environmentally 'crafted' blocks with no simply interchangeable raw material
    if re.match(r'(stripped|carved)_', target_item):
        _get_ingredients_recursive(graph, re.sub(r'^(stripped|carved)_', '', target_item), raw_materials, quantity)
        return True
    
    return False

def _handle_smithing_template(graph: nx.DiGraph, target_item: str, raw_materials: dict, quantity: int):
    """
    If the raw material is a smithing template, we need to include the other ingredients,
    but not the template again.
    """
    if target_item.endswith('_smithing_template'):
        ingredients = list(graph.predecessors(target_item))
        # Remove smithing template from its own list of ingredients to avoid a recursion loop
        ingredients.remove(target_item)
        for ingredient in ingredients:
            weight = graph[ingredient][target_item]['weight']
            _get_ingredients_recursive(graph, ingredient, raw_materials, quantity * weight)

if __name__ == '__main__':
    ...
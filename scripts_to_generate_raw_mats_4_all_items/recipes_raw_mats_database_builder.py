import os
import json
import re

import networkx as nx

from tqdm import tqdm
from collections import defaultdict

from data_scripts.graph_recipes import build_crafting_graph, display_graph_sample, list_crafting_recipes
from constants import IGNORE_ITEMS_REGEX, AXIOM_MATERIALS_REGEX, TAGGED_MATERIALS_BASE, resource_path

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
        
        modified_items = {}
        for ingredient, data in items.items():
            # Change the name of a hashed material inside items to its base material name
            if ingredient.startswith('#'):
                base_material = TAGGED_MATERIALS_BASE[ingredient]
                modified_items[base_material] = data
            else:
                modified_items[ingredient] = data

        if item_name not in raw_materials_cost:
            raw_materials_cost[item_name] = modified_items
        # Only overwrite if shaped or shapeless method
        elif craft_type in ['crafting_shaped', 'crafting_shapeless'] and item_name != 'stick':
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
def get_recipe_data_from_json(folder_path: str = './recipe') -> dict:
    recipe_json_raw_data = {}
    folder_path = resource_path(folder_path)
    # Loop through every recipe.json file
    file_list = [f for f in os.listdir(folder_path) if f.endswith('.json')]
    total_files = len(file_list)

    for filename in tqdm(file_list, total=total_files, desc="Processing files"):
        file_path = os.path.join(folder_path, filename)
        item_name = filename.split('.')[0]
        
        # Load json into the dict
        with open(file_path, 'r') as file:
            item_recipe_data = json.load(file)
            recipe_json_raw_data[item_name] = item_recipe_data

    return recipe_json_raw_data

def add_ingredient(ingredients: dict, item: str):
    # If their are multiple items available, take the shortest name one (most likely to be a raw material)
    item = (item if not isinstance(item, list) else min(item, key=len)).replace('minecraft:', '')
    ingredients[item] = ingredients.setdefault(item, 0) + 1.0

#####################################
### RAW MATERIALS LIST GENERATION ###
#####################################
def generate_master_raw_mats_list(recipe_graph: nx.DiGraph):
    # Open items.json and get items field
    items_path = resource_path('items.json')
    with open(items_path, 'r') as file:
        master_items_list = json.load(file)['items']
    
    master_raw_mats_list = {}
    for item in master_items_list:
        # print(f"Getting raw mats for: {item}")
        master_raw_mats_list[item] = get_ingredients(recipe_graph, item)
    
    with open('raw_materials_table.json', 'w') as f:
        json.dump(master_raw_mats_list, f, indent=4)

def get_ingredients(graph, target_item) -> list[dict]:
    """Lists all raw materials needed to craft a target item, handling circular dependencies."""
    # Convert 'uncraftable' (created outside a crafting table) to their raw base material
    target_item = re.sub(r'^(chipped|damaged)_anvil$', 'anvil', target_item)
    target_item = re.sub(r'(\w+)_concrete$', r'\1_concrete_powder', target_item)
    target_item = re.sub(r'(exposed|weathered|oxidized)_', '', target_item)
    if target_item in ['waxed_copper', 'copper']:
        target_item += '_block'

    # Return single item if it doesn't have a crafting recipe
    if target_item not in graph:
        return [{"item": target_item, "quantity": 1.0}]

    raw_materials = defaultdict(float)
    _get_ingredients_recursive(graph, target_item, raw_materials)

    # Convert to sorted list, highest quantity first, then by item name alphabetically
    return sorted(
        [{"item": item, "quantity": quantity} for item, quantity in raw_materials.items()],
        key=lambda x: (-x["quantity"], x["item"])
    )

def _get_ingredients_recursive(graph, target_item, raw_materials, quantity=1.0):
    """Recursive helper function to find raw materials, handling circular dependencies."""
    # Special case for when an ingot, netherite, isn't actually the raw material
    if target_item == 'netherite_ingot':
        _get_ingredients_recursive(graph, 'netherite_scrap', raw_materials, 4.0 * quantity)
        _get_ingredients_recursive(graph, 'gold_ingot', raw_materials, 4.0 * quantity)
        return
    elif re.match(AXIOM_MATERIALS_REGEX, target_item, re.VERBOSE): # Cycle detected
        raw_materials[target_item] += quantity
        return

    predecessors = list(graph.predecessors(target_item))
    if not predecessors: # Base case: no predecessors, it's a raw material
        raw_materials[target_item] += quantity
        return

    for ingredient in predecessors:
        weight = graph[ingredient][target_item]['weight']
        _get_ingredients_recursive(graph, ingredient, raw_materials, quantity * weight)

if __name__ == '__main__':
    main()

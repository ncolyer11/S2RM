import os
import json
from tqdm import tqdm

# TODO Manage the following edge cases for items with multiple recipes:
# dye_*_carpet, dye_*_bed, 


IGNORE_ITEMS = ['bundle']
TAKE_CRAFTING_METHODS = ['crafting_shaped', 'crafting_shapeless', 'smelting', 'crafting_transumte']
AXIOM_MATERIALS = ['stone', 'cobblestone'] # XXX some materials like iron need to be raw and part of 
# the output but they can be smelted from ore or crafted from blocks or nuggets so you need some way
# to declare that ingots should be considered raw materials and not their other forms

def add_ingredient(ingredients: dict, item: str):
    # If their are multiple items available, just take the first one
    item = (item if not isinstance(item, list) else item[0]).replace('minecraft:', '')
    # If the ingredient isn't already in the dictionary, add it, otherwise increment the count
    ingredients[item] = ingredients.setdefault(item, 0) + 1
        
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
    
    ingredients['count'] = 1
    return ingredients

def get_items_from_craft_type(item_name: str, recipe: dict, craft_type: str) -> dict[str, int]:
    if craft_type == 'crafting_shaped':
        return get_shaped_ingredients(recipe)
    elif craft_type == 'crafting_shapeless':
        return get_shapeless_ingredients(recipe)
    # Smelting recipes only have one ingredient and always of quantity 1
    elif craft_type == 'smelting':
        return get_smelting_ingredients(recipe)
    elif craft_type == 'crafting_transmute':
        return {'shulker_box': 1, recipe['material'].replace('minecraft:', ''): 1, 'count': 1}
    else:
        assert craft_type not in TAKE_CRAFTING_METHODS, \
            "Crafting type not recognised."

        # print(f"Skipping {item_name} with crafting type {craft_type}\n")
        return None

def ignore_item(item_name: str):
    if 'bundle' in item_name:
        item_name = 'bundle'

    if item_name in IGNORE_ITEMS:
        return True

    return False

def get_recipe_data_from_json(folder_path: str = './recipe') -> dict:
    recipe_json_raw_data = {}
    # Loop through the files in the specified folder
    file_list = [f for f in os.listdir(folder_path) if f.endswith('.json')]
    total_files = len(file_list)

    for filename in tqdm(file_list, total=total_files, desc="Processing files"):
        file_path = os.path.join(folder_path, filename)
        item_name = filename.split('.')[0]
        
        # Open and load the JSON file
        with open(file_path, 'r') as file:
            item_recipe_data = json.load(file)
            recipe_json_raw_data[item_name] = item_recipe_data

    return recipe_json_raw_data

def main():
    recipe_json_raw_data = get_recipe_data_from_json()

    # `recipe` here is a dictionary with varying ass keys but always has the 'type' key luckily
    raw_materials_cost = {}
    for item_name, recipe in recipe_json_raw_data.items():
        craft_type = recipe['type'].replace('minecraft:', '')
        if ignore_item(item_name):
            # print(f"Item: {item_name} not needed to schematic materials list")
            continue

        # print(f"Processing {item_name} with crafting type {craft_type}")
        # Return a dictionary of material types and their required quantity
        items = get_items_from_craft_type(item_name, recipe, craft_type)
        if items is None:
            continue
        
        # if craft_type in ['smelting', 'crafting_transmute']:
        #     print(f"Item: {item_name} -> Count: 1")
        # else: 
        #     print(f"Item: {item_name} -> Count: {recipe['result']['count']}")
        
        # Remove text after '_from' to ignore alternate methods
        item_name = item_name.split('_from')[0]
        if item_name not in raw_materials_cost:
            raw_materials_cost[item_name] = items
        # Only overwrite if shaped or shapeless method
        elif craft_type in ['crafting_shaped', 'crafting_shapeless']:
            raw_materials_cost[item_name] = items
        
        # print(f"Ingredients: {items}\n")
    
    for item_name, ingredients in raw_materials_cost.items():
        print(f"Item: {item_name} -> Ingredients: {ingredients}\n")

if __name__ == '__main__':
    main()
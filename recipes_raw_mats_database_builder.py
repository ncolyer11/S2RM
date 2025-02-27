import os
import json

import networkx as nx
import matplotlib.pyplot as plt

from tqdm import tqdm

# TODO Manage the following edge cases for items with multiple recipes:
# dye_*_bed, dye_*_carpet, dye_*_wool
# replace tagged material groups with base material e.g. planks -> oak_planks
# handle recipes where items are left behind, e.g. buckets in cake recipe, bottles in honey block recipe

IGNORE_ITEMS = ['bundle']
TAKE_CRAFTING_METHODS = ['crafting_shaped', 'crafting_shapeless', 'smelting', 'crafting_transumte']
AXIOM_MATERIALS = ['stone', 'cobblestone'] # XXX some materials like iron need to be raw and part of 
# the output but they can be smelted from ore or crafted from blocks or nuggets so you need some way
# to declare that ingots should be considered raw materials and not their other forms
    
######################
### RECIPE RELATED ###
######################
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

def get_items_from_craft_type(recipe: dict, craft_type: str) -> dict[str, int]:
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

        return None

def ignore_item(item_name: str):
    if 'bundle' in item_name:
        item_name = 'bundle'

    if item_name in IGNORE_ITEMS:
        return True

    return False

####################
### RECIPE GRAPH ###
####################
def build_crafting_graph(raw_materials_cost: dict) -> nx.DiGraph:
    G = nx.DiGraph()
    
    for item, ingredients in raw_materials_cost.items():
        count = ingredients.pop('count', 1)  # Number of items produced
        for material, quantity in ingredients.items():
            weight = quantity / count  # How much of material is needed per output item
            G.add_edge(material, item, weight=weight)
    
    return G

def display_graph_sample(graph, target_item, depth=1):
    subgraph_nodes = set([target_item])
    for _ in range(depth):
        new_nodes = set()
        for node in subgraph_nodes:
            new_nodes.update(graph.predecessors(node))  # Get crafting ingredients
        subgraph_nodes.update(new_nodes)

    subgraph = graph.subgraph(subgraph_nodes)
    plt.figure(figsize=(8, 6))
    pos = nx.spring_layout(subgraph)
    nx.draw(subgraph, pos, with_labels=True, node_size=3000, node_color='lightblue', edge_color='gray', font_size=10)
    edge_labels = {(u, v): f"{d['weight']:.2f}" for u, v, d in subgraph.edges(data=True)}
    nx.draw_networkx_edge_labels(subgraph, pos, edge_labels=edge_labels)
    plt.title(f"Crafting Dependencies for {target_item}")
    plt.show()

def find_shortest_crafting_route(graph, start_item, end_item):
    if start_item not in graph or end_item not in graph:
        return None  # Invalid item

    try:
        path = nx.shortest_path(graph, source=start_item, target=end_item, weight='weight')
        return path
    except nx.NetworkXNoPath:
        return None  # No valid path exists

def list_crafting_recipes(graph, target_item):
    if target_item not in graph:
        print(f"No known recipes for {target_item}.")
        return

    print(f"Recipes to craft {target_item}:")
    for ingredient in graph.predecessors(target_item):
        weight = graph[ingredient][target_item]['weight']
        print(f" - {weight:.2f} x {ingredient}")

###############
### HELPERS ###
###############
def get_recipe_data_from_json(folder_path: str = './recipe') -> dict:
    recipe_json_raw_data = {}
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
    # If their are multiple items available, just take the first one
    item = (item if not isinstance(item, list) else item[0]).replace('minecraft:', '')
    # If the ingredient isn't already in the dictionary, add it, otherwise increment the count
    ingredients[item] = ingredients.setdefault(item, 0) + 1


def main():
    print("Building raw materials database from recipe JSON files...")
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
        items = get_items_from_craft_type(recipe, craft_type)
        if items is None:
            # print(f"Skipping {item_name} with crafting type {craft_type}\n")
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
        
    crafting_graph = build_crafting_graph(raw_materials_cost)
    list_crafting_recipes(crafting_graph, 'iron_sword')

if __name__ == '__main__':
    main()

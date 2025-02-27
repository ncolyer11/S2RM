import os
import json
import random
import re

import networkx as nx
import matplotlib.cm as cm
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib import colors

from tqdm import tqdm

# TODO Manage the following edge cases for items with multiple recipes:
# replace tagged material groups with base material e.g. planks -> oak_planks
# handle recipes where items are left behind, e.g. buckets in cake recipe, bottles in honey block recipe
# add a toggle for outputting in blocks vs ingots

IGNORE_ITEMS_REGEX = r'(dye_\w+_(bed|carpet|wool))|bundle'
AXIOM_MATERIALS_REGEX = r"""
    (stone|cobblestone|\w+ingot|slime_ball|redstone|\w+smithing_template|bone_meal|wheat|stick|
    resin_clump|coal|diamond|dried_kelp|emerald|honey_bottle|lapis_lazuli|raw_\w+(?!_block))|\w+dye$
"""

TAKE_CRAFTING_METHODS = ['crafting_shaped', 'crafting_shapeless', 'smelting', 'crafting_transumte']

NODE_COLOUR = '#102d5c'

######################
### RECIPE RELATED ###
######################
def get_raw_materials_cost_dict(recipe_json_raw_data: dict) -> dict:
    raw_materials_cost = {}
    skipped = []
    for item_name, recipe in recipe_json_raw_data.items():
        craft_type = recipe['type'].replace('minecraft:', '')
        if ignore_item(item_name):
            skipped.append(item_name)
            # print(f"Item: {item_name} not needed to schematic materials list")
            continue

        # print(f"Processing {item_name} with crafting type {craft_type}")
        # Return a dictionary of material types and their required quantity
        items = get_items_from_craft_type(recipe, craft_type)
        if items is None:
            # print(f"Skipping {item_name} with crafting type {craft_type}\n")
            skipped.append(item_name)
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
        
    return raw_materials_cost, skipped

def get_items_from_craft_type(recipe: dict, craft_type: str) -> dict[str, int]:
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

def ignore_item(item_name: str):
    if re.match(IGNORE_ITEMS_REGEX, item_name):
        return True

    return False

####################
### RECIPE GRAPH ###
####################
def build_crafting_graph(raw_materials_cost: dict) -> nx.DiGraph:
    G = nx.DiGraph()
    
    for item, ingredients in raw_materials_cost.items():
        count = ingredients.pop('count', 1)
        for material, quantity in ingredients.items():
            weight = quantity / count # How much of material is needed per output item
            G.add_edge(material, item, weight=weight)
    
    return G

def display_graph_sample(graph, target_item, depth=1):
    if target_item == 'all':
        if depth != 1:
            all_nodes = list(graph.nodes())
            if depth > len(all_nodes):
                selected_nodes = all_nodes
            else:
                selected_nodes = random.sample(all_nodes, depth)
            subgraph_nodes = set(selected_nodes)
            for _ in range(3):
                new_nodes = set()
                for node in subgraph_nodes:
                    new_nodes.update(graph.predecessors(node))
                subgraph_nodes.update(new_nodes)
            subgraph = graph.subgraph(subgraph_nodes)
        else:
            subgraph = graph
    else:
        subgraph_nodes = set([target_item])
        for _ in range(depth):
            new_nodes = set()
            for node in subgraph_nodes:
                new_nodes.update(graph.predecessors(node))
            subgraph_nodes.update(new_nodes)
        subgraph = graph.subgraph(subgraph_nodes)

    fig, ax = plt.subplots(figsize=(17, 8.5), facecolor='#2a2a2a')
    ax.set_facecolor('#1a1a1a')

    pos = nx.spring_layout(subgraph, k=0.5, iterations=50)

    node_degrees = dict(subgraph.degree())
    min_degree = min(node_degrees.values())
    max_degree = max(node_degrees.values())
    if min_degree == max_degree:
        node_sizes = [200 for _ in subgraph.nodes()]
    else:
        node_sizes = [((node_degrees[node] - min_degree) / (max_degree - min_degree) * 1500) + 200 for node in subgraph.nodes()]

    node_colors = [NODE_COLOUR for _ in subgraph.nodes()]
    nodes = nx.draw_networkx_nodes(subgraph, pos, node_size=node_sizes, node_color=node_colors, ax=ax)
    labels = nx.draw_networkx_labels(subgraph, pos, font_size=5, font_color='#ededed', ax=ax)  # Slightly larger, grey-blue labels

    edge_colors = []
    for u, v, d in subgraph.edges(data=True):
        weight_uv = d['weight']
        weight_vu = graph.get_edge_data(v, u, {}).get('weight', None)
        if weight_vu is not None:
            avg_weight = (weight_uv + weight_vu) / 2
        else:
            avg_weight = weight_uv
        edge_colors.append(avg_weight)

    max_weight = max(edge_colors)
    min_weight = min(edge_colors)
    if min_weight == max_weight:
        normalized_weights = edge_colors
    else:
        normalized_weights = [(w - min_weight) / (max_weight - min_weight) for w in edge_colors]

    cmap = cm.get_cmap('RdPu')

    edge_colors = [cmap(w) for w in normalized_weights]

    nx.draw_networkx_edges(subgraph, pos, edge_color=edge_colors, ax=ax)

        # sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=min_weight, vmax=max_weight))
        # sm.set_array([])
        # cbar = plt.colorbar(sm, label="Average Edge Weight", ax=ax, shrink=0.7)
        # cbar.ax.yaxis.label.set_color('white')
        # cbar.ax.tick_params(colors='white')


    # if target_item != 'all':
    #     plt.title(f"Crafting Dependencies for {target_item}", color='white')
    # else:
    #     plt.title("Entire Crafting Graph - Edges Colored by Average Weight", color='white')

    def on_pick(event):
        ind = event.ind[0]
        node = list(subgraph.nodes())[ind]

        highlighted_nodes = {node}  # Start with the selected node

        # Expand highlighted nodes up to depth 5
        nodes_to_explore = [(node, 0)]  # (node, depth)
        while nodes_to_explore:
            current_node, depth = nodes_to_explore.pop(0)
            if depth < 5:
                neighbors = set(subgraph.neighbors(current_node)) - highlighted_nodes
                for neighbor in neighbors:
                    highlighted_nodes.add(neighbor)
                    nodes_to_explore.append((neighbor, depth + 1))

        node_colors = []
        for n in subgraph.nodes():
            if n not in highlighted_nodes:
                node_colors.append(NODE_COLOUR)
            else:
                if n == node:
                    node_colors.append('#c4aa00')  # Selected node is a slightly darker yellow
                else:
                    # Calculate desaturated orange based on depth
                    node_depth = 0
                    nodes_to_check = [(node, 0)]  # (node, depth)
                    visited = {node}
                    while n not in visited and nodes_to_check:
                        current_node, depth = nodes_to_check.pop(0)
                        if n in subgraph.neighbors(current_node):
                            node_depth = depth + 1
                            break
                        if depth < 5:
                            neighbors = set(subgraph.neighbors(current_node)) - visited
                            for neighbor in neighbors:
                                nodes_to_check.append((neighbor, depth + 1))
                                visited.add(neighbor)

                    desaturation_factor = min(node_depth / 5.0, 1.0)  # Desaturate more with depth
                    r, g, b = colors.hex2color('#ffa500')  # Orange in RGB
                    r = r + (1 - r) * desaturation_factor
                    g = g + (1 - g) * desaturation_factor
                    b = b + (1 - b) * desaturation_factor
                    node_colors.append(colors.rgb2hex((r, g, b)))

        nodes.set_facecolor(node_colors)
        fig.canvas.draw_idle()

    nodes.set_picker(True)
    fig.canvas.mpl_connect('pick_event', on_pick)

    plt.tight_layout()
    plt.show()

def list_crafting_recipes(graph, target_item):
    """
    Lists all raw materials needed to craft a target item, handling circular dependencies.
    """

    if target_item not in graph:
        print(f"No known recipes for {target_item}.")
        return

    raw_materials = set()
    visited = set() # Track visited nodes to detect cycles
    _list_crafting_recipes_recursive(graph, target_item, raw_materials, visited)

    if raw_materials:
        print(f"Raw materials needed to craft {target_item}:")
        for material, quantity in raw_materials:
            print(f"- {quantity:.2f} x {material}")
    else:
        print(f"No raw materials found for {target_item}.")

def _list_crafting_recipes_recursive(graph, target_item, raw_materials, visited, quantity=1.0):
    """
    Recursive helper function to find raw materials, handling circular dependencies.
    """
    if re.match(AXIOM_MATERIALS_REGEX, target_item, re.VERBOSE): # Cycle detected
        raw_materials.add((target_item, quantity))
        return

    visited.add(target_item)

    predecessors = list(graph.predecessors(target_item))
    if not predecessors: # Base case: no predecessors, it's a raw material
        raw_materials.add((target_item, quantity))
        visited.remove(target_item)
        return

    for ingredient in predecessors:
        weight = graph[ingredient][target_item]['weight']
        _list_crafting_recipes_recursive(graph, ingredient, raw_materials, visited, quantity * weight)

    visited.remove(target_item)

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
    # If their are multiple items available, take the shortest name one (most likely to be a raw material)
    item = (item if not isinstance(item, list) else min(item, key=len)).replace('minecraft:', '')
    ingredients[item] = ingredients.setdefault(item, 0) + 1.0

def generate_master_raw_mats_list(recipe_graph: nx.DiGraph):
    # Open items.json and get items field
    with open('items.json', 'r') as file:
        master_items_list = json.load(file)['items']
    
    master_raw_mats_list = {}
    for item in master_items_list:
        # print(f"Getting raw mats for: {item}")
        master_raw_mats_list[item] = get_ingredients(recipe_graph, item)
    
    with open('raw_materials_table.json', 'w') as f:
        json.dump(master_raw_mats_list, f, indent=4)
    

def get_ingredients(graph, target_item) -> list[dict]:
    """
    Lists all raw materials needed to craft a target item, handling circular dependencies.
    """
    # Return single item if it doesn't have a crafting recipe
    if target_item not in graph:
        return [{"item": target_item, "quantity": 1.0}]

    raw_materials = set()
    visited = set() # Track visited nodes to detect cycles
    _get_ingredients_recursive(graph, target_item, raw_materials, visited)

    return [{"item": item, "quantity": quantity} for item, quantity in raw_materials]

def _get_ingredients_recursive(graph, target_item, raw_materials, visited, quantity=1.0):
    """
    Recursive helper function to find raw materials, handling circular dependencies.
    """
    if re.match(AXIOM_MATERIALS_REGEX, target_item, re.VERBOSE): # Cycle detected
        print(f"Axiomatic detected: {target_item}")
        raw_materials.add((target_item, quantity))
        return

    visited.add(target_item)

    predecessors = list(graph.predecessors(target_item))
    if not predecessors: # Base case: no predecessors, it's a raw material
        raw_materials.add((target_item, quantity))
        visited.remove(target_item)
        return

    for ingredient in predecessors:
        weight = graph[ingredient][target_item]['weight']
        _list_crafting_recipes_recursive(graph, ingredient, raw_materials, visited, quantity * weight)

    visited.remove(target_item)

def main():
    recipe_json_raw_data = get_recipe_data_from_json()
    raw_materials_cost, skipped = get_raw_materials_cost_dict(recipe_json_raw_data)
    # for item_name, ingredients in raw_materials_cost.items():
    #     print(f"Item: {item_name} -> Ingredients: {ingredients}\n")
        
    recipe_graph = build_crafting_graph(raw_materials_cost)
    generate_master_raw_mats_list(recipe_graph)
    
    # list_crafting_recipes(recipe_graph, 'chiseled_resin_bricks')
    # display_graph_sample(recipe_graph, 'chiseled_resin_bricks', depth=7)
    # display_graph_sample(recipe_graph, 'all', depth=500)

if __name__ == '__main__':
    main()

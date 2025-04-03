import re
import random

import networkx as nx
import matplotlib.cm as cm
import matplotlib.pyplot as plt

from matplotlib import colors

from src.constants import NODE_COLOUR, AXIOM_MATERIALS_REGEX

############################
### RECIPE GRAPH RELATED ###
############################
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
    labels = nx.draw_networkx_labels(subgraph, pos, font_size=5, font_color='#ededed', ax=ax)

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
                    node_colors.append('#c4aa00')
                else:
                    # Calculate desaturated orange based on depth
                    node_depth = 0
                    nodes_to_check = [(node, 0)] # (node, depth)
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

                    desaturation_factor = min(node_depth / 5.0, 1.0) # Desaturate more with depth
                    r, g, b = colors.hex2color('#ffa500')
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

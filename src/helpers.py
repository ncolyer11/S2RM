import json
import re
import os
import requests

from tqdm import tqdm
from dataclasses import dataclass

from src.use_config import get_config_value
from src.resource_path import resource_path
from src.constants import BLOCK_TAGS, DF_STACK_SIZE, GAME_DATA_DIR, LIMTED_STACKS_NAME, \
    SHULKER_BOX_SIZE

@dataclass
class TableCols:
    input_items: list
    input_quantities: list
    exclude: list
    raw_materials: list
    raw_quantities: list
    collected_data: list

    def reset(self):
        self.input_items = []
        self.input_quantities = []
        self.exclude = []
        self.raw_materials = []
        self.raw_quantities = []
        self.collected_data = []

def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))

def add_material(materials: dict[str, int], item: str, count:int = 1):
    """Helper function to add materials safely."""
    materials[item] = materials.get(item, 0) + count

def verify_regexes(search_str: str) -> list[str] | bool:
    """Check if the search terms are valid regexes and return a list of valid search terms."""
    if not (search_terms := [term.strip().strip("'") for term in search_str.split(",") if term.strip()]):
        return False
    valid_search_terms = []
    for term in search_terms:
        try:
            re.compile(term)
            valid_search_terms.append(term)
        except re.error:
            pass
    
    if not valid_search_terms:
        return False

    return valid_search_terms

def download_file(url, output_path) -> bool:
    """Download a file with a progress bar."""
    output_path = resource_path(output_path)
    try:
        # Send GET request and then raise an exception for bad HTTP status codes
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Get the total file size for tracking progress
        total_size = int(response.headers.get('content-length', 0))
        # Open the output file in binary write mode and start a progress bar
        with open(output_path, 'wb') as file, \
             tqdm(
                desc=os.path.basename(output_path),
                total=total_size,
                colour='green',
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
             ) as progress_bar:
            
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                progress_bar.update(size)
        
        print(f"Successfully downloaded {url} to path {output_path}\n")
        return True
    
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def format_quantities(materials: list[str], qs_vals_text: tuple[list[int], list[str]],
                      is_exclude_col: bool = False) -> None:
    """
    Format the quantities of items in terms of shulker boxes, stacks, and individual items.

    Parameters
    ----------
    materials : list[str]
        The list of materials.
    qs_vals_text : tuple[list[int], list[str]]
        A tuple containing the quantities as integers and as formatted strings.
    is_exclude_col : bool, optional
        Whether to use shorthand names for item stacks and shulker boxes in exclude column. Defaults to False.

    Raises
    ------
    TypeError
        If the materials and quantities lists are not the same length.    
    """
    quantity_vals, quantity_text = qs_vals_text

    if not (len(materials) == len(quantity_vals) == len(quantity_text)):
        raise TypeError("Materials and quantities lists must be the same length.\n"
                        f"Got {len(materials)} materials, {len(quantity_vals)} quantities_int and "
                        f"{len(quantity_text)} quantities_text.")

    for i, (material, quantity) in enumerate(zip(materials, quantity_vals)):
        formatted_quantity = get_shulkers_stacks_and_items(quantity, material, is_exclude_col)
        quantity_text[i] = formatted_quantity

def get_shulkers_stacks_and_items(quantity: int, item_name: str = "", shorthand: bool = False,
                                  limited_stack_items: dict[str, int] | None = None) -> str:
    """
    Return a formatted string of the quantity in the form of 'x (y SB + z stacks + a)'.
    
    Parameters
    ----------
    quantity : int
        The quantity of items.
    item_name : str, optional
        The name of the item, used to determine the stack size. Defaults to "".
    shorthand : bool, optional
        Whether to use shorthand names for item stacks and shulker boxes. Defaults to False.
    limited_stack_items : dict[str, int], optional
        A dictionary mapping item names to their stack sizes. Defaults to None. If none, read dict
        from the currently selected mc version data folder.
    
    Returns
    -------
    str
        The formatted string representing the quantity in terms of shulker boxes, stacks, and individual items.
    """
    # Shulkers can't be stacked and also can't be put in other shulker boxes
    if "shulker_box" in item_name:
        return str(int(quantity))

    # Determine the stack size for this item
    if limited_stack_items is None:
        limited_stack_items = get_limit_stack_items()

    stack_size = limited_stack_items.get(item_name, DF_STACK_SIZE)
    # Calculate how many items fit in a shulker box
    shulker_box_capacity = stack_size * SHULKER_BOX_SIZE
    
    # Calculate the components
    num_shulker_boxes = quantity // shulker_box_capacity
    remaining_after_shulkers = quantity % shulker_box_capacity
    
    # For items that stack
    if stack_size > 1:
        num_stacks = remaining_after_shulkers // stack_size
        remaining_items = remaining_after_shulkers % stack_size
    # For non-stacking items (stack_size == 1)
    else:
        num_stacks = 0 # No concept of "stacks" for unstackable items
        remaining_items = remaining_after_shulkers
    
    # Generate the output string
    if shorthand:
        parts = []
        if num_shulker_boxes > 0:
            parts.append(f"{int(num_shulker_boxes)}sb")
        
        if stack_size > 1 and num_stacks > 0:
            parts.append(f"{int(num_stacks)}s")
            
        if remaining_items > 0:
            parts.append(f"{int(remaining_items)}")
        
        return " ".join(parts) or "0"
    else:
        # Start with the total quantity
        result = f"{int(quantity)}"
        
        # Only add parentheses if we have something to break down
        has_breakdown = num_shulker_boxes > 0 or (stack_size > 1 and num_stacks > 0)
        
        if has_breakdown:
            parts = []
            if num_shulker_boxes > 0:
                parts.append(f"{int(num_shulker_boxes)} SB")
            
            if stack_size > 1 and num_stacks > 0:
                parts.append(f"{int(num_stacks)} stack")
                if num_stacks > 1:
                    parts[-1] += "s"
                
            if remaining_items > 0:
                parts.append(f"{int(remaining_items)}")
                
            if parts:
                result += f" ({' + '.join(parts)})"
                
        return result

def get_limit_stack_items(version="current"):
    """
    Load a dictionary containing all items that don't stack to 64, and their stack size (either
    16 or 1).
    """
    try:
        if version == "current":
            version = get_config_value("selected_mc_version")

        with open(resource_path(os.path.join(GAME_DATA_DIR, version, LIMTED_STACKS_NAME)), "r") as f:
            return json.load(f)
    except FileNotFoundError as e:
        print(f"File {LIMTED_STACKS_NAME} not found in {GAME_DATA_DIR}/{version}: {e}")
        return None

def print_formatted_entity_data(entity_data):
    """Print out the data of an entity.data object from the litemapy library in a formatted way."""
    print()
    entity_name = entity_data.get("id", "").replace("minecraft:", "")
    print(f"Entity: {entity_name}")
    for key, value in entity_data.items():
        if key != 'Items':
            print(f"\t{key}: {value}")
        else:
            print(f"\t{key}:")
            for item in value:
                print(f"\t\t{item}")
    print()

def int_to_roman(n: int) -> str:
    """Convert an integer to a Roman numeral, between 1 and 3999."""
    if not 1 <= n <= 3999:
        raise ValueError("Roman Numerals Range is and must be between 1 and 3999, inclusive.")
    
    roman_numerals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"),
        (1, "I")
    ]
    
    result = ""
    for value, numeral in roman_numerals:
        while n >= value:
            result += numeral
            n -= value
        
    return result

def convert_block_to_item(block_name: str) -> list[str]:
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

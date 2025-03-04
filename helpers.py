import re
import os
import sys

from dataclasses import dataclass

from constants import DF_STACK_SIZE, SHULKER_BOX_SIZE, LIMITED_STACK_ITEMS

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

def add_material(materials, item, count=1):
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

def get_shulkers_stacks_and_items(quantity: int, item_name: str = "", shorthand: bool = False) -> str:
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
    
    Returns
    -------
    str
        The formatted string representing the quantity in terms of shulker boxes, stacks, and individual items.
    """
    # Shulkers can't be stacked and also can't be put in other shulker boxes
    if "shulker_box" in item_name:
        return str(quantity)

    # Determine the stack size for this item
    stack_size = LIMITED_STACK_ITEMS.get(item_name, DF_STACK_SIZE)
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
        result = f"{quantity}"
        
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

# Helper
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

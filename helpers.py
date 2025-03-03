import re
import os
import sys

from constants import DF_STACK_SIZE, SHULKER_BOX_SIZE, LIMITED_STACK_ITEMS

def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))

def verify_regexes(search_terms: list[str]) -> str:
    """Check if the search terms are valid regexes and return a list of valid search terms."""
    valid_search_terms = []
    for term in search_terms:
        try:
            re.compile(term)
            valid_search_terms.append(term)
        except re.error:
            pass

    return valid_search_terms

def format_quantities(total_materials: dict[str, int]|list[int],
                      shorthand: bool = False) -> list[str] | None:
    """
    If total_materials is a list of numbers, just output a formatted list of numbers. Otherwise,
    format the total_materials dictionary.
    """
    # XXX neeed to fix this so it only accepts dicts as it needs material data for stack size
    if isinstance(total_materials, list):
        return [get_shulkers_stacks_and_items(quantity, shorthand=shorthand)
                for quantity in total_materials]
    elif isinstance(total_materials, dict):
        for material, quantity in total_materials.items():
            # check type of quantity
            if isinstance(quantity, str):
                quantity = int(quantity.split("(")[0].strip())
            total_materials[material] = get_shulkers_stacks_and_items(quantity, material, shorthand)
    else:
        raise TypeError("total_materials must be a list or dictionary.")

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
        num_stacks = 0  # No concept of "stacks" for unstackable items
        remaining_items = remaining_after_shulkers
    
    # Generate the output string
    if shorthand:
        parts = []
        if num_shulker_boxes > 0:
            parts.append(f"{num_shulker_boxes}sb")
        
        if stack_size > 1 and num_stacks > 0:
            parts.append(f"{num_stacks}s")
            
        if remaining_items > 0:
            parts.append(f"{remaining_items}")
        
        return " ".join(parts)
    else:
        # Start with the total quantity
        result = f"{quantity}"
        
        # Only add parentheses if we have something to break down
        has_breakdown = num_shulker_boxes > 0 or (stack_size > 1 and num_stacks > 0)
        
        if has_breakdown:
            parts = []
            if num_shulker_boxes > 0:
                parts.append(f"{num_shulker_boxes} SB")
            
            if stack_size > 1 and num_stacks > 0:
                parts.append(f"{num_stacks} stack")
                if num_stacks > 1:
                    parts[-1] += "s"
                
            if remaining_items > 0:
                parts.append(f"{remaining_items}")
                
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

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
        Whether to use shorthand names item stacks and shulker boxes. Defaults to False.
    """
    stack_size = LIMITED_STACK_ITEMS.get(item_name, DF_STACK_SIZE)
    shulker_box_stack_size = stack_size * SHULKER_BOX_SIZE

    if shorthand:
        output_string = ""

        num_shulker_boxes = quantity // shulker_box_stack_size
        if num_shulker_boxes:
            output_string += f"{num_shulker_boxes}sb "

        remaining_stacks = (quantity % shulker_box_stack_size) // stack_size
        if remaining_stacks:
            output_string += f"{remaining_stacks}s "

        remaining_items = quantity % stack_size
        if remaining_items:
            output_string += f"{remaining_items}"

        return output_string.strip()

    else:
        output_string = f"{quantity}"

        if quantity >= stack_size:
            output_string += " ("

        num_shulker_boxes = quantity // shulker_box_stack_size
        if num_shulker_boxes:
            output_string += f"{num_shulker_boxes} SB"

        remaining_stacks = (quantity % shulker_box_stack_size) // stack_size
        if remaining_stacks:
            if num_shulker_boxes:
                output_string += " + "
            output_string += f"{remaining_stacks} stacks"

        remaining_items = quantity % stack_size
        if remaining_items:
            if num_shulker_boxes or remaining_stacks:
                output_string += " + "
            output_string += f"{remaining_items}"

        if quantity >= stack_size:
            output_string += ")"

        return output_string

# Helper
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

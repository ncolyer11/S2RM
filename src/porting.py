from dataclasses import asdict

from src.helpers import format_quantities, TableCols
from src.constants import OUTPUT_JSON_VERSION

NO_ERR = 0    # No Error
IV_ERR = 1    # Incompatible Version Error
CJ_ERR = 2    # Corrupt JSON Error

OUTPUT_JSON_DEFAULT = {
    "version": OUTPUT_JSON_VERSION,
    "material_list_paths": [],
    "output_type": "",
    "ice_type": "",
    "input_items": [],
    "input_quantities": [],
    "exclude_text": [],
    "raw_materials": [],
    "raw_quantities": [],
    "collected": {}
}

def get_error_message(ec: int, version: int) -> str:
    """Return the error message for the given error code."""
    error_messages = {
        IV_ERR: (
            "Warning: The materials table you are trying to open is uses an incompatible format.\n\n"
            f"Expected version: '{OUTPUT_JSON_VERSION}'.\nFound Version: '{version}'.\n\n"
            "Porting is not supported between these versions.\n"
            "Therefore, the selected materials table cannot be opened."
        ),
        CJ_ERR: (
            "Warning: The materials table you are trying to open is corrupted.\n\n"
            "Regardless of its version, it contained a mix of complete and incomplete fields which "
            "conflicted with each other.\n\n"
            "Therefore, the selected materials table cannot be opened."
        ),
    }
    
    return error_messages.get(ec, "An unknown error occurred.")

def forwardportJson(table_dict, version: int) -> int:
    """
    Forwardport a materials table dictionary to the latest version.
    
    Porting is not supported if the program's json version is below 3, or if the input version is
    below 2 (unspecified), or if the input version is higher than the program's json version.
    
    Returns:
        True if successful, otherwise an error code.
    """
    if not isinstance(version, int) or version <= 2 or OUTPUT_JSON_VERSION <= 3 \
            or version > OUTPUT_JSON_VERSION:
        return print_forwardporting_error(version, IV_ERR)
    
    forwardport_methods = {
        4: forwardporttoV4,
        5: forwardporttoV5,
        6: forwardporttoV6,
        7: forwardporttoV7,
        8: forwardporttoV8
    }
    
    # forwardport successively to the target version
    try:
        for target_version in range(version + 1, OUTPUT_JSON_VERSION + 1):
            if target_version in forwardport_methods:
                print(f"Forwardporting from version {version} to {target_version}.")
                if error_code := forwardport_methods[target_version](table_dict):
                    return print_forwardporting_error(version, error_code)
    except (KeyError, TypeError, ValueError, IndexError):
        return print_forwardporting_error(version, CJ_ERR)
     
    # Each group of columns must be either all populated or all empty
    tv = table_dict["tv"]
    if not (bool(tv["input_items"]) == bool(tv["input_quantities"]) == bool(tv["exclude"])):
        return CJ_ERR
    if not (bool(tv["raw_materials"]) == bool(tv["raw_quantities"])):
        return CJ_ERR

    table_dict["version"] = OUTPUT_JSON_VERSION

    return NO_ERR

######### Forwardporting Methods #########

def forwardporttoV4(table_dict):
    """Versions below 4 didn't have the 'output_type' and 'ice_type' fields."""
    table_dict.setdefault("output_type", "ingots")
    table_dict.setdefault("ice_type", "ice")

def forwardporttoV5(table_dict):
    """Versions below 5 didn't guarantee that all fields would be populated."""
    # We must loop through all the keys and add any that are missing
    for key, defalut_value in OUTPUT_JSON_DEFAULT.items():
        if key not in table_dict:
            table_dict[key] = defalut_value
        else:
            # Remove and re-add the key to maintain order
            original_table_dict_val = table_dict[key]
            del table_dict[key]
            table_dict[key] = original_table_dict_val
    
def forwardporttoV6(table_dict):
    """Versions below 6 used a single input materials path called 'litematica_mats_list_path'."""
    if path := table_dict.pop("litematica_mats_list_path", None):
        table_dict["material_list_paths"] = [path]

def forwardporttoV7(table_dict):
    """
    Versions below 7 don't have the exclude_values field instead of exclude_input (now formatted).
    Also, an exclude_text field has been added to track the SB and stacks format.
    """
    table_dict["exclude_values"] = table_dict.pop("exclude_input", [])
    table_dict["exclude_text"] = list(table_dict["exclude_values"])
    if not table_dict["exclude_values"]:
        return

    excl_list = [table_dict["exclude_values"], table_dict["exclude_text"]]
    format_quantities(table_dict["input_items"], excl_list, is_exclude_col=True)

def forwardporttoV8(table_dict):
    """
    In between v7 and v8 was a massive refactor that moved everything into self.tv, and self.tt,
    meaning table values and table text, respectively.
    """
    tv = TableCols([], [], [], [], [], [])
    tv.input_items = table_dict.pop("input_items", [])
    tv.input_quantities = table_dict.pop("input_quantities", [])
    tv.exclude = table_dict.pop("exclude_values", [])
    tv.raw_materials = table_dict.pop("raw_materials", [])
    tv.raw_quantities = table_dict.pop("raw_quantities", [])

    # Older files stored 'collected' as a dict or as a list that may not line up with the rows
    collected = table_dict.pop("collected", [])
    if isinstance(collected, dict):
        tv.collected_data = [bool(collected.get(m)) for m in tv.raw_materials]
    else:
        tv.collected_data = [bool(c) for c in collected][:len(tv.raw_materials)]
        tv.collected_data += [False] * (len(tv.raw_materials) - len(tv.collected_data))

    tt = TableCols(**{key: list(value) for key, value in asdict(tv).items()})
    tt.exclude = table_dict.pop("exclude_text", [])
    if tv.input_items:
        format_quantities(tv.input_items, (tv.input_quantities, tt.input_quantities))
    if tv.raw_materials:
        format_quantities(tv.raw_materials, (tv.raw_quantities, tt.raw_quantities))

    table_dict["tv"] = asdict(tv)
    table_dict["tt"] = asdict(tt)

# Helper function to print forwardporting error message
def print_forwardporting_error(version, ec):
    if ec == NO_ERR:
        print(f"Successfully forwardported from v{version} to v{OUTPUT_JSON_VERSION}.")
        return True
    else:
        print(f"There was an error ({ec}) whilst forwardporting from v{version} to v{OUTPUT_JSON_VERSION}.")
        return ec

import json
from helpers import format_quantities

NO_ERR = 0    # No Error
IV_ERR = 1    # Incompatible Version Error
CJ_ERR = 2    # Corrupt JSON Error

OUTPUT_JSON_VERSION = 8 # Track the version of the output json files for forwardporting capability
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
    if version <= 2 or OUTPUT_JSON_VERSION <= 3 or version > OUTPUT_JSON_VERSION:
        return print_forwardporting_error(version, IV_ERR)
    
    forwardport_methods = {
        4: forwardporttoV4,
        5: forwardporttoV5,
        6: forwardporttoV6,
        7: forwardporttoV7,
        8: forwardporttoV8
    }
    
    # forwardport successively to the target version
    for target_version in range(version + 1, OUTPUT_JSON_VERSION + 1):
        if target_version in forwardport_methods:
            print(f"Forwardporting from version {version} to {target_version}.")
            if error_code := forwardport_methods[target_version](table_dict):
                return print_forwardporting_error(version, error_code)
     
    # If any one of the following lists are empty, then they all should be, otherwise we have an error   
    if not (bool(table_dict["input_items"]) == bool(table_dict["input_quantities"])
        == bool(table_dict["exclude_text"]) == bool(table_dict["exclude_values"])):
        return CJ_ERR
    # Same with 'raw_materials' and 'raw_quantities'
    if not (bool(table_dict["raw_materials"]) == bool(table_dict["raw_quantities"])):
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
    table_dict["material_list_paths"] = [table_dict.pop("litematica_mats_list_path")] \
    if "litematica_mats_list_path" in table_dict else []

def forwardporttoV7(table_dict):
    """
    Versions below 7 don't have the exclude_values field instead of exclude_input (now formatted).
    Also, an exclude_text field has been added to track the SB and stacks format.
    """
    table_dict["exclude_values"] = table_dict.pop("exclude_input") \
    if "exclude_input" in table_dict else []
    # XXX this needs to be formatted differently using xsb ys z, and also needs to pass in the input
    # name so the function can work out the stack size
    table_dict["exclude_text"] = format_quantities(table_dict["exclude_values"])

def forwardporttoV8(table_dict):
    ...

# Helper function to print forwardporting error message
def print_forwardporting_error(version, ec):
    if ec == NO_ERR:
        print(f"Successfully forwardported from v{version} to v{OUTPUT_JSON_VERSION}.")
        return True
    else:
        print(f"There was an error ({ec}) whilst forwardporting from v{version} to v{OUTPUT_JSON_VERSION}.")
        return ec

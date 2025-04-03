"""Simple API ish thing to handle accessing, setting, resetting, and printing config.json"""

import json

from src.resource_path import resource_path
from src.constants import PROGRAM_VERSION, CONFIG_PATH

DF_CONFIG = {
    "program_version": PROGRAM_VERSION,
    "declined_latest_program_version": False, # XXX rn this will never show up if the user declines
    "selected_mc_version": "1.21.5",
    "latest_mc_version": "1.21.5",
    "declined_latest_mc_version": False # change this to a timestamp or something
}

def create_default_config():
    """Creates a default config file with the default settings."""
    try:
        with open(resource_path(CONFIG_PATH), "w") as f:
            json.dump(DF_CONFIG, f, indent=4)
    except (FileNotFoundError, PermissionError, IOError) as e:
        print(f"Error creating default config file: {e}")
        raise e
    
def get_config_value(key):
    """Get a value from config.json. Raises KeyError if key doesn't exist."""
    try:
        with open(resource_path(CONFIG_PATH), "r") as f:
            config = json.load(f)
            if key not in config:
                raise KeyError(f"Config key '{key}' not found in config.json for getting.")
            
            return config[key]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise e

def set_config_value(key, value):
    """Helper function to set any value in config.json with a single line."""
    try:
        with open(resource_path(CONFIG_PATH), "r") as f:
            config = json.load(f)
        
        if key not in config:
            raise KeyError(f"Config key '{key}' not found in config.json for setting.")
        
        config[key] = value
        with open(resource_path(CONFIG_PATH), "w") as f:
            json.dump(config, f, indent=4)

    except (FileNotFoundError, json.JSONDecodeError)as e:
        print(f"Error setting config value: {key}")
        raise e
    
    return True

def print_config():
    """Prints the config.json file in a readable format."""
    try:
        with open(resource_path(CONFIG_PATH), "r") as f:
            config = json.load(f)
            print(json.dumps(config, indent=4))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error printing config file: {e}")
        raise e

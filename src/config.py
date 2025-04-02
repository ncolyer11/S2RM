import json
from s2rm.src.constants import CONFIG_PATH, ICON_PATH, PROGRAM_VERSION
from s2rm.src.helpers import resource_path, get_latest_s2rm_release
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

DF_CONFIG = {
    "program_version": PROGRAM_VERSION,
    "declined_latest_program_version": False,
    "selected_mc_version": "1.21.5",
    "latest_mc_version": "1.21.5",
    "declined_latest_mc_version": False
}

def update_config():
    """
    Check if anything in the users program needs updating (the program itself, mc version etc)
    based off their config.json file.
    """
    # Check if PROGRAM_VERSION matches with the one in config.json
    if get_config_value("program_version") != PROGRAM_VERSION:
        # Update the config.json file with the new version
        set_config_value("program_version", PROGRAM_VERSION)
    
    
    # Check S2RM Github repo for if there's a newer version (release) of the program
    if (latest_s2rm := get_latest_s2rm_release()) != PROGRAM_VERSION:
        # Check if the user has declined the latest version
        if not get_config_value("declined_latest_version"):
            print(f"New version available: {latest_s2rm}.")
            print("Please update to the latest version for the best experience.")
            # Ask the user if they want to decline the latest version
            decline = input("Do you want to decline this version? (y/n): ").strip().lower()
            if decline == "y":
                set_config_value("declined_latest_version", True)
                print("You have declined the latest version.")
    
def create_default_config():
    """
    Creates a default config file with the default settings.
    """
    # Create the default config file
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

def prompt_update(latest_s2rm):
    if not get_config_value("declined_latest_version"):
        # Create a QApplication instance if one doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        app.setWindowIcon(QIcon(resource_path(ICON_PATH)))
        app.setStyle('Fusion')

        # Create and configure message box
        msgBox = QMessageBox()
        msgBox.setWindowTitle("New Version Available")
        msgBox.setText(f"A new version ({latest_s2rm}) is available.")
        msgBox.setInformativeText("Would you like to update now?")
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        
        # Check the user's response
        response = msgBox.exec()
        app.quit()

        if response == QMessageBox.No:
            set_config_value("declined_latest_version", True)

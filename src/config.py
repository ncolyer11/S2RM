import json
import requests
import webbrowser

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from src.constants import CONFIG_PATH, ICON_PATH, PROGRAM_VERSION, S2RM_API_RELEASES_URL, S2RM_RELEASES_URL, \
    constants_py_resource_path as resource_path

DF_CONFIG = {
    "program_version": PROGRAM_VERSION,
    "declined_latest_program_version": False, # XXX rn this will never show up if the user declines
    "selected_mc_version": "1.21.5",
    "latest_mc_version": "1.21.5",
    "declined_latest_mc_version": False # change this to a timestamp or something
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
        prompt_program_update(latest_s2rm)
    
    # Update config with the latest mc version
    if get_config_value("latest_mc_version") != (latest_mc_version := get_current_mc_version()[0]):
        set_config_value("latest_mc_version", latest_mc_version)
    
    # Check if the selected Minecraft version is the latest
    if get_config_value("selected_mc_version") != latest_mc_version:
        prompt_mc_update(latest_mc_version)
    
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

def prompt_program_update(latest_s2rm):
    if not get_config_value("declined_latest_program_version"):
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
        msgBox.setStandardButtons(QMessageBox.No | QMessageBox.Yes)
        msgBox.setDefaultButton(QMessageBox.Yes)

        # Rename buttons
        msgBox.button(QMessageBox.Yes).setText("Update")
        msgBox.button(QMessageBox.No).setText("Decline")

        # Check the user's response
        response = msgBox.exec()
        app.quit()

        if response == QMessageBox.No:
            set_config_value("declined_latest_program_version", True)
        elif response == QMessageBox.Yes:
            webbrowser.open(S2RM_RELEASES_URL)  # Open the GitHub releases page

def prompt_mc_update(latest_mc_version: str):
    if not get_config_value("declined_latest_mc_version"):
        # Create a QApplication instance if one doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        app.setWindowIcon(QIcon(resource_path(ICON_PATH)))
        app.setStyle('Fusion')

        # Create and configure message box
        msgBox = QMessageBox()
        msgBox.setWindowTitle("New Minecraft Version Available")
        msgBox.setText(f"A new Minecraft version ({latest_mc_version}) is available.")
        msgBox.setInformativeText("Would you like to update now?")
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        
        # Check the user's response
        response = msgBox.exec()
        app.quit()

        if response == QMessageBox.No:
            set_config_value("declined_latest_mc_version", True)
        elif response == QMessageBox.Yes:
            set_config_value("selected_mc_version", latest_mc_version)

def get_latest_s2rm_release() -> str:
    """
    Get the latest release version of the S2RM program from GitHub.
    
    Raises
    ------
    ValueError
        If the latest release name is not found in the response.
    """
    try:
        response = requests.get(S2RM_API_RELEASES_URL)
        response.raise_for_status()
        release_data = response.json()
        latest_release = release_data.get("name", None)
        if latest_release is None:
            raise ValueError("Latest release name not found in response.")
        # Remove the "v" prefix if it exists
        return latest_release.lstrip("v")
    except Exception as e:
        print(f"Error fetching latest release version: {e}")
        raise e

def get_current_mc_version() -> tuple[str, str]:
    """
    Fetch the latest Minecraft version (including snapshots) from Mojang's version manifest.
    
    Returns
    -------
    tuple[str, str]
        A tuple containing the latest version ID and its download URL.

    Raises
    ------
    ValueError
        If no latest version is found in the manifest.
    """
    version_manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    
    response = requests.get(version_manifest_url)
    response.raise_for_status()
    version_data = response.json()
    
    latest_version = version_data['latest']['snapshot']
    
    # Find the download URL for this version
    for version in version_data['versions']:
        if version['id'] == latest_version:
            return latest_version, version['url']
    
    raise ValueError("No latest version or URL found in the manifest")
    
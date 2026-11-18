import json
import os
import webbrowser

import requests

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from src.use_config import get_config_value, set_config_value, create_default_config
from src.resource_path import resource_path
from src.constants import CONFIG_PATH, GAME_DATA_DIR, ICON_PATH, \
    PROGRAM_VERSION, RAW_MATS_TABLE_NAME, S2RM_API_RELEASES_URL, S2RM_RELEASES_URL
from data.download_game_data import get_latest_mc_version
from src.game_data_sync import covers, is_supported, sync_published_game_data
from src.versioned_json import apply_versioned_payload, resolve_best_version, version_key

def update_config(redownload=False, delete=True):
    """
    Check if anything in the users program needs updating (the program itself, mc version etc)
    based off their config.json file.
    """
    # Check if PROGRAM_VERSION matches with the one in config.json
    if get_config_value("program_version") != PROGRAM_VERSION:
        # Update the config.json file with the new version
        set_config_value("program_version", PROGRAM_VERSION)
    
    # Don't bother updating mc game files if not connected to the internet
    if not check_connection():
        return
    
    # Check S2RM Github repo for if there's a newer version (release) of the program
    if is_newer_release(latest_s2rm := get_latest_s2rm_release(), PROGRAM_VERSION):
        prompt_program_update(latest_s2rm)
    
    # Update config with the latest mc version
    try:
        latest_mc_version = get_latest_mc_version()[0]
    except (requests.RequestException, ValueError) as exc:
        print(f"Could not reach Mojang's version manifest: {exc}")
        return
    if get_config_value("latest_mc_version") != latest_mc_version:
        set_config_value("latest_mc_version", latest_mc_version)
    
    # only offer a new version once its data has been published
    published_version = sync_published_game_data(latest_mc_version)
    if get_config_value("selected_mc_version") != latest_mc_version \
            and covers(published_version, latest_mc_version):
        prompt_mc_update(latest_mc_version)
        
    # Check if the user has the selected mc version downloaded
    check_has_selected_mc_vers(redownload, delete)
    
def check_has_selected_mc_vers(redownload: bool = False, delete=True) -> bool | str:
    """
    Make sure the data for the selected version is available. Returns True if it already was,
    False if it had to be downloaded, or "issue" if the newest available version was selected
    instead. redownload forces a refresh; delete is unused.
    """
    selected_mc_version = get_config_value("selected_mc_version")
    if is_supported(selected_mc_version) and not redownload:
        return True

    available = sync_published_game_data(None if redownload else selected_mc_version)
    if is_supported(selected_mc_version):
        return False

    print(f"Game data for {selected_mc_version} isn't available. "
          f"Falling back to the newest available version ({available}).")
    if available is not None:
        set_config_value("selected_mc_version", available)
    return "issue"

def check_connection() -> bool:
    """Check if the user is connected to the internet and if the config file exists."""
    try:
        requests.get("https://www.google.com", timeout=5)
    except requests.ConnectionError:
        print("No internet connection. Skipping game data download.")
        return False
    except requests.Timeout:
        print("Connection timed out. Skipping game data download.")
        return False
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return False

    # Check if the config file exists
    if not os.path.exists(resource_path(CONFIG_PATH)):
        print("Config file not found. Generating a new default config file "
              "and skipping game data download.")
        create_default_config()
        return False
    
    return True

def get_materials_table(version="current"):
    """
    Load the raw materials table containing the number of raw materials required to craft one
    of each item.
    """
    try:
        if version == "current":
            version = get_config_value("selected_mc_version")

        with open(resource_path(os.path.join(GAME_DATA_DIR, RAW_MATS_TABLE_NAME)), "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict) or "version" not in data:
            return data

        available_versions = [key for key in data.keys() if key != "version"]
        target_version = resolve_best_version(available_versions, version)
        if target_version is None:
            raise ValueError(f"No materials table available for Minecraft {version}.")

        return apply_versioned_payload(data, target_version)
    except FileNotFoundError as e:
        print("Error: Raw materials table not found.")
        raise e

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
        msgBox.setWindowTitle("New S2RM Version Available")
        msgBox.setText(f"A new version of S2RM ({latest_s2rm}) is available.")
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
            webbrowser.open(S2RM_RELEASES_URL)

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
        
        # Rename buttons
        msgBox.button(QMessageBox.Yes).setText("Update")
        msgBox.button(QMessageBox.No).setText("Decline")
        
        # Check the user's response
        response = msgBox.exec()
        app.quit()

        if response == QMessageBox.No:
            set_config_value("declined_latest_mc_version", True)
        elif response == QMessageBox.Yes:
            set_config_value("selected_mc_version", latest_mc_version)
            check_has_selected_mc_vers()

def is_newer_release(latest: str, current: str) -> bool:
    try:
        return version_key(latest) > version_key(current)
    except ValueError:
        return False

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

#############################################
################## HELPERS ##################
#############################################

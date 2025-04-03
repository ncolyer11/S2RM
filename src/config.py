import json
import os
import shutil
import requests
import webbrowser

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from src.use_config import get_config_value, set_config_value, create_default_config
from src.resource_path import resource_path
from src.constants import BLOCKS_JSON, CONFIG_PATH, DATA_DIR, ENTITIES_JSON, GAME_DATA_DIR, GAME_DATA_FILES, ICON_PATH, ITEMS_JSON, \
    LIMTED_STACKS_NAME, MC_DOWNLOADS_DIR, PROGRAM_VERSION, RAW_MATS_TABLE_NAME, S2RM_API_RELEASES_URL, \
        S2RM_RELEASES_URL
from data.parse_mc_data import cleanup_downloads, create_mc_data_dirs, \
    parse_blocks_list, parse_entities_list, parse_items_list, parse_items_stack_sizes, \
        save_json_file
from data.download_game_data import download_game_data, get_latest_mc_version
from data.recipes_raw_mats_database_builder import generate_raw_materials_table_dict

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
    if (latest_s2rm := get_latest_s2rm_release()) != PROGRAM_VERSION:
        prompt_program_update(latest_s2rm)
    
    # Update config with the latest mc version
    if get_config_value("latest_mc_version") != (latest_mc_version := get_latest_mc_version()[0]):
        set_config_value("latest_mc_version", latest_mc_version)
    
    # Check if the selected Minecraft version is the latest
    if get_config_value("selected_mc_version") != latest_mc_version:
        prompt_mc_update(latest_mc_version)
        
    # Check if the user has the selected mc version downloaded
    check_has_selected_mc_vers(redownload, delete)
    
def check_has_selected_mc_vers(redownload: bool = False, delete=True) -> bool | str:
    """
    Check if the selected Minecraft version has the required data files in its data/game folder.

    Parameters
    ----------
    redownload : bool
        Force redownload of game data and recalculate the materials table.
    delete : bool
        Delete the mc_downloads directory after downloading the game data.

    Returns
    -------
    bool
        True if the selected version is already downloaded, False if the selected version is not 
        found and had to be redownloaded.
    """
    # Remove MC_DOWNLOADS_DIR if it exists just to be sure
    try:
        shutil.rmtree(resource_path(MC_DOWNLOADS_DIR))
    except FileNotFoundError:
        pass
    
    selected_mc_version = get_config_value("selected_mc_version")
    # Check if the selected version has raw_materials_table and limited_stack_items.json files
    if has_data_files(selected_mc_version) and not redownload:
        return True

    # At this point, the user would've already been prompted to update the programs selected mc
    # version to the latest one.
    # So if the files for the selected mc version aren't found, then we need to redownload the
    # mc files, parse them, and reconstruct the raw_materials_table and limited_stack_items.jsons
    actually_downloaded_version = download_game_data(selected_mc_version)
    issue_downloading = False
    if actually_downloaded_version != selected_mc_version:
        print("Issue downloading the selected version. "
              "Backup version downloaded and set as selected instead.")
        issue_downloading = "issue"

    set_config_value("selected_mc_version", actually_downloaded_version)

    # Generate raw_materials_table and limited_stack_items.json files
    # using the downloaded and parsed game data
    if not has_data_files(actually_downloaded_version):
        get_mats_table_and_lim_stacked_items(delete)

    if issue_downloading:
        return issue_downloading
    
    return False

def has_data_files(version: str) -> bool:
    """
    Check if the specified version has the required data files in it's data/game folder:
    - RAW_MATS_TABLE_NAME
    - LIMTED_STACKS_NAME
    """
    # Check if the version has the required data files
    version_path = resource_path(os.path.join(GAME_DATA_DIR, version))
    raw_mats_table_path = os.path.join(version_path, RAW_MATS_TABLE_NAME)
    limited_stacks_path = os.path.join(version_path, LIMTED_STACKS_NAME)

    return (
        os.path.exists(version_path) and
        os.path.exists(raw_mats_table_path) and
        os.path.exists(limited_stacks_path)
    )

def get_mats_table_and_lim_stacked_items(delete=True):
    """
    Parse the Minecraft game data and save it to JSON files after parsing.
    
    XXX remove cache and replace it with a manual tool to delete specific downloaded versions (plus a clear all (but selected) option)

    Parameters
    ----------
    delete : bool, optional
        Whether to delete the excess game data files after parsing (default is True)
    """
    # Get the selected Minecraft version
    selected_mc_version = get_config_value("selected_mc_version")
    
    # Create the 'data/game' directories
    create_mc_data_dirs(selected_mc_version)
    
    # Parse and save items list
    items_list = parse_items_list()
    save_json_file(selected_mc_version, ITEMS_JSON, items_list)
    
    # Parse and save entities list
    entities_list = parse_entities_list()
    save_json_file(selected_mc_version, ENTITIES_JSON, entities_list)
    
    # Parse and save blocks list
    blocks_list = parse_blocks_list()
    save_json_file(selected_mc_version, BLOCKS_JSON, blocks_list)
    
    # Parse item stack sizes
    items_stack_sizes = parse_items_stack_sizes()
    
    # Construct the raw materials table using graphs
    raw_mats_table = generate_raw_materials_table_dict(selected_mc_version)
    
    # Remove the downloads directory if specified
    if delete:
        cleanup_downloads()
    
    # Empty the data/game/<mc_version> directory if it exists
    version_dir = resource_path(os.path.join(GAME_DATA_DIR, selected_mc_version))
    if os.path.exists(version_dir):
        for filename in GAME_DATA_FILES:
            file_path = os.path.join(version_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Removed {file_path}")
    
    # Save both important data files to the data/game/<mc_version> directory
    save_json_file(selected_mc_version, LIMTED_STACKS_NAME, items_stack_sizes)
    save_json_file(selected_mc_version, RAW_MATS_TABLE_NAME, raw_mats_table)

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
            
        with open(resource_path(os.path.join(GAME_DATA_DIR, version, RAW_MATS_TABLE_NAME)), "r") as f:
            return json.load(f)
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
        
        # Check the user's response
        response = msgBox.exec()
        app.quit()

        if response == QMessageBox.No:
            set_config_value("declined_latest_mc_version", True)
        elif response == QMessageBox.Yes:
            set_config_value("selected_mc_version", latest_mc_version)
            check_has_selected_mc_vers(latest_mc_version)

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

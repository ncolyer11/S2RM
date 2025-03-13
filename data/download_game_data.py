import os
import json
import shutil
import requests
import zipfile

from tqdm import tqdm
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from src.constants import CONFIG_PATH, GAME_DATA_DIR, ICON_PATH, MC_DOWNLOADS_DIR, GAME_DATA_FILES
from src.helpers import download_file, resource_path
from data.parse_mc_data import calculate_materials_table

# TODO: finish logic for this. consider redoing to make all folder creation and deletion happen at
# one point in the program for reliability. also add better handling for temp folders etc
def check_mc_data(redownload: bool = False, delete=True) -> bool:
    """
    Search for latest mc version from manifest and compare to the program's current version
    stored in config.json.

    Downloading the latest version is optional, so if a new version is found the user should be 
    prompted to select to download this version or not with a pop-up window (using pyside 6.qt)
    
    Parameters
    ----------
    redownload : bool
        Force redownload of game data and recalculate the materials table.
    delete : bool
        Delete the mc_downloads directory after downloading the game data.

    Returns
    -------
    bool
        True if the latest version is already downloaded, False if the latest version is not found.
    """
    # Get the latest version from the manifest
    latest_version, _ = get_latest_minecraft_version()

    # Check all currently downloaded version to see if the latest version is already downloaded
    matching_versions = False
    if not os.path.exists(resource_path(GAME_DATA_DIR)):
        os.makedirs(resource_path(GAME_DATA_DIR), exist_ok=True)
    else:
        for version in os.listdir(resource_path(GAME_DATA_DIR)):
            if version == latest_version:
                matching_versions = True
                break

    # Compare the two versions
    if matching_versions:
        # Folder could exist but not all the files
        if not os.path.exists(resource_path(os.path.join(GAME_DATA_DIR, latest_version))) or not all(
            os.path.exists(resource_path(os.path.join(GAME_DATA_DIR, latest_version, f))) for f in GAME_DATA_FILES
        ):
            print("Game data files not found. Downloading new data and updating materials table now...")

        # Else check if the user is forcing a redownload
        elif redownload:
            print("Versions match but redownload is forced. Downloading new data and updating "
                  "materials table now...")
        else:
            print(f"Latest MC data found in program: {latest_version}.")
            # Return early to avoid unnecessary downloads and recalculating the materials table
            return matching_versions

    # If the latest version was not found, prompt the user to download the new version
    else:
        # Create a QApplication instance if one doesn't exist
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        app.setWindowIcon(QIcon(resource_path(ICON_PATH)))
        app.setStyle('Fusion')
        # Create and configure message box
        msgBox = QMessageBox()
        msgBox.setWindowTitle("New Minecraft Version Available")
        msgBox.setText(f"A new Minecraft version ({latest_version}) is available.")
        msgBox.setInformativeText("Would you like to download this version?")
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        
        # Check the user's response
        response = msgBox.exec()

        # Close the application instance
        app.quit()

        # If the user selects No, return early
        if response != QMessageBox.Yes:
            return matching_versions
        print(f"Latest MC data not found in program: {latest_version}. "
              "Downloading new data and updating materials table now...")

    download_game_data()
    calculate_materials_table(delete)

    return matching_versions

def get_latest_minecraft_version() -> tuple:
    """Fetch the latest Minecraft version (including snapshots) from Mojang's version manifest."""
    version_manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    
    try:
        response = requests.get(version_manifest_url)
        response.raise_for_status()
        version_data = response.json()
        
        latest_version = version_data['latest']['snapshot']
        
        # Find the download URL for this version
        for version in version_data['versions']:
            if version['id'] == latest_version:
                return latest_version, version['url']
        
        raise ValueError("Could not find latest version")
    
    except Exception as e:
        print(f"Error fetching version: {e}")
        return None, None

def download_game_data(specific_version=None):
    repo_path = "NikitaCartes-archive/MinecraftDeobfuscated-Mojang"
    files_to_download = [
        ('minecraft/src/net/minecraft/world/item/Items.java',
         os.path.join(MC_DOWNLOADS_DIR, 'Items.java')),
        ('minecraft/src/net/minecraft/world/level/block/Blocks.java',
         os.path.join(MC_DOWNLOADS_DIR, 'Blocks.java')),
        ('minecraft/src/net/minecraft/world/entity/EntityType.java',
         os.path.join(MC_DOWNLOADS_DIR, 'EntityType.java'))
    ]
   
    # Delete any existing minecraft_downloads folder
    try:
        shutil.rmtree(MC_DOWNLOADS_DIR)
    except FileNotFoundError:
        pass
    
    # Create the downloads directory
    os.makedirs(MC_DOWNLOADS_DIR, exist_ok=True)
    
    # If specific version is provided, get the url for that version
    if specific_version:
        version_id = specific_version
        version_url = get_minecraft_version_url(version_id)
    # Otherwise, find and retrieve the latest version
    else:
        version_id, version_url = get_latest_minecraft_version()
   
    # Download .java game files from GitHub using specific version if provided
    for file_path, output_path in files_to_download:
        git_downloaded = download_github_file(repo_path, file_path, output_path, version_id)

    if version_id and version_url:
        jar_downloaded = download_minecraft_jar(version_id, version_url)
    
    # Cleanup the JAR file after extraction and update the config with the latest version if successful
    if git_downloaded and jar_downloaded:
        # Read, modify, and then write back the config file, changing it's mc version
        with open(resource_path(CONFIG_PATH), "r") as f:
            config = json.load(f)
        config["mc_version"] = version_id
        config["latest_mc_version"] = get_latest_minecraft_version()[0]
        with open(resource_path(CONFIG_PATH), "w") as f:
            json.dump(config, f, indent=4)

        # Remove the downloaded .jar file
        cleanup_jar_file(version_id)
    else:
        print("Failed to download game data. Removing the downloads directory...")
        shutil.rmtree(MC_DOWNLOADS_DIR)

def get_minecraft_version_url(version_id: str) -> str | None:
    """
    Get the version URL from the Mojang version manifest.
    
    Parameters
    ----------
    version_id : str
        The Minecraft version ID to get the URL for. If "latest", get the latest snapshot version.
    
    Returns
    -------
    str
        The URL for the specific version ID. If not found, return None.
    """
    try:
        # Get the version manifest
        manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
        response = requests.get(manifest_url)
        response.raise_for_status()
        manifest = response.json()
        
        # Find the specific version in the manifest
        if version_id == "latest":
            version_id = manifest["latest"]["snapshot"]
        
        for version in manifest["versions"]:
            if version["id"] == version_id:
                return version["url"]
        
        print(f"Version {version_id} not found in the manifest")
        return None
    except Exception as e:
        print(f"Failed to get version URL for {version_id}: {e}")
        return None

def get_latest_github_file_url(repo_path, file_path):
    """Get the latest raw file URL from the GitHub repository"""
    # GitHub API URL to get the latest commit for the file
    # Source: https://docs.github.com/en/rest/reference/repos#commits
    api_url = f"https://api.github.com/repos/{repo_path}/commits?path={file_path}&page=1&per_page=1"
   
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        commits = response.json()
       
        if not commits:
            raise ValueError(f"No commits found for {file_path}")
       
        return f"https://raw.githubusercontent.com/{repo_path}/{commits[0]['sha']}/{file_path}"
   
    except Exception as e:
        print(f"Error fetching latest file URL for {file_path}: {e}")
        return None

def download_github_file(repo_path, file_path, output_path, specific_version=None) -> bool:
    try:
        if specific_version:
            # Use the specific version as the commit
            raw_url = f"https://raw.githubusercontent.com/{repo_path}/{specific_version}/{file_path}"
        else:
            # Get the latest version URL
            if not (raw_url := get_latest_github_file_url(repo_path, file_path)):
                print(f"Could not get URL for {file_path}")
                return False
       
        return download_file(raw_url, output_path)
   
    except Exception as e:
        print(f"Error downloading {file_path}: {e}")
        return False

def download_minecraft_jar(version_id, version_url) -> bool:
    """Download the Minecraft version JAR and extract recipes and item JSONs"""
    try:
        version_meta_response = requests.get(version_url)
        version_meta_response.raise_for_status()
        version_meta = version_meta_response.json()
        
        jar_url = version_meta['downloads']['client']['url']
        jar_path = os.path.join(MC_DOWNLOADS_DIR, f'{version_id}.jar')
        if not download_file(jar_url, jar_path):
            return False
        
        # Open the JAR file
        with zipfile.ZipFile(jar_path, 'r') as jar:
            os.makedirs(os.path.join(MC_DOWNLOADS_DIR, 'recipe'), exist_ok=True)
            
            # Extract all recipe JSON files and copy them into the MC_DOWNLOADS_DIR/recipe folder
            recipe_files = [
                f for f in jar.namelist() 
                if f.startswith('data/minecraft/recipe/') and f.endswith('.json')
            ]
            for recipe_file in tqdm(recipe_files, desc="Extracting Recipes", colour='blue'):
                recipe_path = os.path.join(MC_DOWNLOADS_DIR, f'recipe/{os.path.basename(recipe_file)}')
                with jar.open(recipe_file) as source, \
                        open(resource_path(recipe_path), 'wb') as target:
                    target.write(source.read())
            
            print(f"Extracted {len(recipe_files)} recipe JSON files")
            os.makedirs(os.path.join(MC_DOWNLOADS_DIR, 'items'), exist_ok=True)
                    
            # Extract all item JSON files and copy them into the MC_DOWNLOADS_DIR/items folder
            item_files = [
                f for f in jar.namelist() 
                if f.startswith('assets/minecraft/items/') and f.endswith('.json')
            ]
            for item_file in tqdm(item_files, desc="Extracting Item JSONs", colour='blue'):
                item_path = os.path.join(MC_DOWNLOADS_DIR, f'items/{os.path.basename(item_file)}')
                with jar.open(item_file) as source, \
                    open(item_path, 'wb') as target:
                    target.write(source.read())
            
            print(f"Extracted {len(item_files)} item JSON files")

            if not recipe_files or not item_files:
                print("No recipe or item JSON files found in the JAR")
                return False

        print(f"Successfully downloaded and extracted resources for version {version_id}\n")
        return True
    
    except Exception as e:
        print(f"Error downloading and extracting Minecraft JAR: {e}")
        return False

def cleanup_jar_file(version_id):
    """Remove the downloaded JAR file after extracting the recipes."""
    jar_path = os.path.join(MC_DOWNLOADS_DIR, f'{version_id}.jar')
    
    try:
        # Check if file exists before attempting to remove
        if os.path.exists(jar_path):
            os.remove(jar_path)
            print(f"Cleaned up JAR file: {jar_path}")
        else:
            print(f"JAR file not found: {jar_path}")
    except Exception as e:
        print(f"Error removing JAR file: {e}")

if __name__ == '__main__':
    download_game_data()

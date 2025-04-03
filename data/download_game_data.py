import os
import shutil
import requests
import zipfile

from tqdm import tqdm

from src.resource_path import resource_path
from src.helpers import download_file, resource_path
from src.constants import BACKUP_VERSION, GAME_DATA_DIR, MC_CODE_REPO_URL, MC_CODE_TO_DOWNLOAD, \
    MC_DOWNLOADS_DIR

def check_mc_version_in_program_exists(mc_version: str) -> bool:
    """
    Check if a given mc version has a folder in game data with a materials table, limited
    stacked items list etc.
    """
    matching_versions = False
    if not os.path.exists(resource_path(GAME_DATA_DIR)):
        os.makedirs(resource_path(GAME_DATA_DIR), exist_ok=True)
    else:
        for version in os.listdir(resource_path(GAME_DATA_DIR)):
            if version == mc_version:
                matching_versions = True
                break
    
    return matching_versions

def download_game_data(specific_version = None, fix_redownload = False) -> str:
    # Delete any existing minecraft_downloads folder
    try:
        print(f"Deleting dir: {resource_path(MC_DOWNLOADS_DIR)}")
        shutil.rmtree(resource_path(MC_DOWNLOADS_DIR))
    except FileNotFoundError:
        pass
    
    # Create the downloads directory
    os.makedirs(resource_path(MC_DOWNLOADS_DIR), exist_ok=False)
    
    # If specific version is provided, get the url for that version
    if specific_version:
        version_id, version_url = specific_version, get_minecraft_version_url(specific_version)
    # Otherwise, find and retrieve the latest version
    else:
        version_id, version_url = get_current_mc_version()
   
    # Download .java game files from GitHub using specific version if provided
    git_downloaded, jar_downloaded = False, False
    for file_path, output_path in MC_CODE_TO_DOWNLOAD:
        if download_github_file(MC_CODE_REPO_URL, file_path, output_path, version_id):
            git_downloaded = True

    if version_id and version_url:
        jar_downloaded = download_minecraft_jar(version_id, version_url)
    
    # Cleanup the JAR file after extraction and ensure config selected version is set
    if git_downloaded and jar_downloaded:
        cleanup_jar_file(version_id)
        print(f"successfully downloaded game data for version {version_id}")
        return version_id
    else:
        shutil.rmtree(resource_path(MC_DOWNLOADS_DIR))
        print(f"\nFailed to download game data: git: {git_downloaded}, jar: {jar_downloaded}. "
              f"Removing downloads directory.\n"
              f"Downloading backup version {BACKUP_VERSION} instead...\n")
        if not fix_redownload:
            if not check_mc_version_in_program_exists(BACKUP_VERSION):
                return download_game_data(BACKUP_VERSION, fix_redownload=True)
            else:
                print(f"Game data already exists for backup version {BACKUP_VERSION}.")
                return BACKUP_VERSION
        else:
            raise ValueError(F"Failed to download to backup version: {BACKUP_VERSION}.")

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
        # Logic for downloading the version.jar file from Mojang
        version_meta_response = requests.get(version_url)
        version_meta_response.raise_for_status()
        version_meta = version_meta_response.json()
        
        jar_url = version_meta['downloads']['client']['url']
        jar_path = resource_path(os.path.join(MC_DOWNLOADS_DIR, f'{version_id}.jar'))
        if not download_file(jar_url, jar_path):
            return False
        
        # Open the JAR file
        with zipfile.ZipFile(jar_path, 'r') as jar:
            recipe_files = extract_recipe_jsons(jar)
            item_files = extract_item_jsons(jar)

            if not recipe_files or not item_files:
                print("No recipe or item JSON files found in the JAR.\n"
                      f"Recipes: {len(recipe_files)}, items: {len(item_files)}")
                return False

        print(f"Successfully downloaded and extracted resources for version {version_id}\n")
        return True
    
    except Exception as e:
        print(f"Error downloading and extracting Minecraft JAR: {e}")
        return False

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

def cleanup_jar_file(version_id):
    """Remove the downloaded JAR file after extracting the recipes."""
    jar_path = resource_path(os.path.join(MC_DOWNLOADS_DIR, f'{version_id}.jar'))
    
    try:
        # Check if file exists before attempting to remove
        if os.path.exists(jar_path):
            os.remove(jar_path)
            print(f"Cleaned up JAR file: {jar_path}")
        else:
            print(f"JAR file not found: {jar_path}")
    except Exception as e:
        print(f"Error removing JAR file: {e}")

def extract_recipe_jsons(jar: zipfile.ZipFile) -> list[str]:
    os.makedirs(resource_path(os.path.join(MC_DOWNLOADS_DIR, 'recipe')), exist_ok=True)
    
    # Extract all recipe JSON files and copy them into the resource_path(MC_DOWNLOADS_DIR)/recipe folder
    recipe_files = [
        f for f in jar.namelist() 
        if f.startswith('data/minecraft/recipe/') and f.endswith('.json')
    ]
    for recipe_file in tqdm(recipe_files, desc="Extracting Recipes", colour='blue'):
        recipe_path = resource_path(os.path.join(MC_DOWNLOADS_DIR, 
                                                    f'recipe/{os.path.basename(recipe_file)}'))
        with jar.open(recipe_file) as source, open(recipe_path, 'wb') as target:
            target.write(source.read())
    
    print(f"Extracted {len(recipe_files)} recipe JSON files")
    
    return recipe_files
    
def extract_item_jsons(jar: zipfile.ZipFile) -> list[str]:
    # Extract all item JSON files and copy them into the resource_path(MC_DOWNLOADS_DIR)/items folder
    os.makedirs(resource_path(os.path.join(MC_DOWNLOADS_DIR, 'items')), exist_ok=True)
    item_files = [
        f for f in jar.namelist() 
        if f.startswith('assets/minecraft/items/') and f.endswith('.json')
    ]
    for item_file in tqdm(item_files, desc="Extracting Item JSONs", colour='blue'):
        item_path = resource_path(os.path.join(MC_DOWNLOADS_DIR, f'items/{os.path.basename(item_file)}'))
        with jar.open(item_file) as source, \
            open(item_path, 'wb') as target:
            target.write(source.read())
    
    print(f"Extracted {len(item_files)} item JSON files")

    return item_files

if __name__ == '__main__':
    download_game_data("1.21.5")

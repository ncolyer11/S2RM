import os
import json
import shutil
import requests
import zipfile

from tqdm import tqdm
from data.parse_mc_data import calculate_materials_table

def check_mc_version() -> bool:
    """
    Search for latest mc version from manifest and compare to the program's current version
    stored in config.json.
    """
    # Get the latest version from the manifest
    latest_version, _ = get_latest_minecraft_snapshot()

    # Get the current version from config.json
    with open("config.json", "r") as f:
        config = json.load(f)
        current_version = config.get("mc_version", None)

    # Compare the two versions
    if matching_versions := latest_version == current_version:
        print(f"MC data is up to date with the latest version: {latest_version}.")
    # Recalculate the materials table if new data is available
    else:
        print(f"MC data is not up to date with the latest version: {latest_version}, "
              f"was: {current_version}. Downloading new data and updating materials table now...")
        download_game_data()
    calculate_materials_table() # XXX run everytime for now

    return matching_versions

def download_file(url, output_path):
    """Download a file with a progress bar."""
    try:
        # Send GET request and then raise an exception for bad HTTP status codes
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Get the total file size for tracking progress
        total_size = int(response.headers.get('content-length', 0))
        # Open the output file in binary write mode and start a progress bar
        with open(output_path, 'wb') as file, \
             tqdm(
                desc=os.path.basename(output_path),
                total=total_size,
                colour='green',
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
             ) as progress_bar:
            
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                progress_bar.update(size)
        
        print(f"Successfully downloaded {url}\n")
        return True
    
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

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

def download_github_file(repo_path, file_path, output_path):
    try:
        if not (raw_url := get_latest_github_file_url(repo_path, file_path)):
            print(f"Could not get URL for {file_path}")
            return
        
        download_file(raw_url, output_path)
    
    except Exception as e:
        print(f"Error downloading {file_path}: {e}")

def get_latest_minecraft_snapshot() -> tuple:
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

def download_minecraft_jar(version_id, version_url):
    """Download the Minecraft version JAR and extract recipes and item JSONs"""
    try:
        version_meta_response = requests.get(version_url)
        version_meta_response.raise_for_status()
        version_meta = version_meta_response.json()
        
        jar_url = version_meta['downloads']['client']['url']
        jar_path = f'minecraft_downloads/{version_id}.jar'
        if not download_file(jar_url, jar_path):
            return None
        
        # Open the JAR file
        with zipfile.ZipFile(jar_path, 'r') as jar:
            os.makedirs('minecraft_downloads/recipe', exist_ok=True)
            
            # Extract all recipe JSON files
            recipe_files = [
                f for f in jar.namelist() 
                if f.startswith('data/minecraft/recipe/') and f.endswith('.json')
            ]
            for recipe_file in tqdm(recipe_files, desc="Extracting Recipes", colour='blue'):
                with jar.open(recipe_file) as source, \
                     open(f'minecraft_downloads/recipe/{os.path.basename(recipe_file)}', 'wb') as target:
                    target.write(source.read())
                    
            os.makedirs('minecraft_downloads/items', exist_ok=True)
                    
            # Extract all item JSON files
            item_files = [
                f for f in jar.namelist() 
                if f.startswith('assets/minecraft/items/') and f.endswith('.json')
            ]
            for item_file in tqdm(item_files, desc="Extracting Item JSONs", colour='blue'):
                with jar.open(item_file) as source, \
                     open(f'minecraft_downloads/items/{os.path.basename(item_file)}', 'wb') as target:
                    target.write(source.read())
            
            print(f"Extracted {len(item_files)} item JSON files")
        
        
        print(f"Successfully downloaded and extracted resources for version {version_id}\n")
        return version_id
    
    except Exception as e:
        print(f"Error downloading Minecraft JAR: {e}")
        return None

def cleanup_jar_file(version_id):
    """Remove the downloaded JAR file after extracting the recipes."""
    jar_path = f'minecraft_downloads/{version_id}.jar'
    
    try:
        # Check if file exists before attempting to remove
        if os.path.exists(jar_path):
            os.remove(jar_path)
            print(f"Cleaned up JAR file: {jar_path}")
        else:
            print(f"JAR file not found: {jar_path}")
    except Exception as e:
        print(f"Error removing JAR file: {e}")

def download_game_data():
    repo_path = "NikitaCartes-archive/MinecraftDeobfuscated-Mojang"
    files_to_download = [
        ('minecraft/src/net/minecraft/world/item/Items.java', 'minecraft_downloads/Items.java'),
        ('minecraft/src/net/minecraft/world/level/block/Blocks.java', 'minecraft_downloads/Blocks.java'),
        ('minecraft/src/net/minecraft/world/entity/EntityType.java', 'minecraft_downloads/EntityType.java')
    ]
    
    # Delete any exisiting minecraft_downloads folder
    try:
        shutil.rmtree("minecraft_downloads")
    except FileNotFoundError:
        pass

    # Download GitHub files using the latest commit
    for file_path, output_path in files_to_download:
        download_github_file(repo_path, file_path, output_path)
    
    # Get and download latest Minecraft snapshot
    version_id, version_url = get_latest_minecraft_snapshot()
    if version_id and version_url:
        download_result = download_minecraft_jar(version_id, version_url)
        # Cleanup the JAR file after extraction and update the config with the latest version
        if download_result:
            # Read the config file
            with open("config.json", "r") as f:
                config = json.load(f)
            
            # Update the version field
            config["mc_version"] = download_result
            
            # Write the updated config back to the file
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)


            cleanup_jar_file(version_id)

if __name__ == '__main__':
    download_game_data()
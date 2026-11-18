"""Helpers for querying Mojang's version manifest (no game files are downloaded here)."""
import requests

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

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
        response = requests.get(MANIFEST_URL, timeout=15)
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

def get_latest_mc_version(level: str = "release") -> tuple[str, str]:
    """
    Fetch the latest Minecraft version (including snapshots) from Mojang's version manifest.
    
    Parameters
    ----------
    level : str
        The level of version to fetch. If != "release", fetch the latest snapshot version.
    
    Returns
    -------
    tuple[str, str]
        A tuple containing the latest version ID and its download URL.

    Raises
    ------
    ValueError
        If no latest version is found in the manifest.
    """
    response = requests.get(MANIFEST_URL, timeout=15)
    response.raise_for_status()
    version_data = response.json()
    
    # Determine the latest version based on the specified level
    if level == "release":
        latest_version = version_data['latest']['release']
    else:
        latest_version = version_data['latest']['snapshot']
    
    # Find the download URL for this version
    for version in version_data['versions']:
        if version['id'] == latest_version:
            return latest_version, version['url']
    
    raise ValueError("No latest version or URL found in the manifest")

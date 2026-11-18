"""Downloads the pre-built recipe and stack size data published in the repo."""
from __future__ import annotations

import json
import os
import tempfile
from typing import Optional

import requests

from src.constants import GAME_DATA_DIR, LIMTED_STACKS_NAME, PUBLISHED_GAME_DATA_URL, \
    RAW_MATS_TABLE_NAME
from src.resource_path import resource_path
from src.versioned_json import version_key

_TIMEOUT = 15
PUBLISHED_FILES = (RAW_MATS_TABLE_NAME, LIMTED_STACKS_NAME)


def _fetch_json(filename: str) -> dict:
    response = requests.get(f"{PUBLISHED_GAME_DATA_URL}/{filename}", timeout=_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
        raise ValueError(f"{filename} is not a valid versioned game data file.")
    return payload


def local_data_version() -> Optional[str]:
    """Newest Minecraft version covered by the local data, or None."""
    versions = []
    for filename in PUBLISHED_FILES:
        path = resource_path(os.path.join(GAME_DATA_DIR, filename))
        try:
            with open(path, "r", encoding="utf-8") as handle:
                versions.append(json.load(handle).get("version"))
        except (OSError, json.JSONDecodeError, AttributeError):
            return None
    if not all(isinstance(v, str) for v in versions):
        return None
    try:
        return min(versions, key=version_key)
    except ValueError:
        return None


def local_versions() -> list[str]:
    """Minecraft versions with local data, newest first."""
    path = resource_path(os.path.join(GAME_DATA_DIR, RAW_MATS_TABLE_NAME))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            keys = {key for key in json.load(handle) if key != "version"}
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if (newest := local_data_version()) is not None:
        keys.add(newest)
    return sorted(keys, key=version_key, reverse=True)


def covers(data_version: Optional[str], mc_version: str) -> bool:
    """Whether data built up to data_version includes mc_version."""
    try:
        return data_version is not None and version_key(data_version) >= version_key(mc_version)
    except ValueError:
        return False


def is_supported(mc_version: str) -> bool:
    """Whether the local data spans mc_version (between its oldest and newest versions)."""
    versions = local_versions()
    try:
        return bool(versions) and version_key(versions[-1]) <= version_key(mc_version) \
            and covers(local_data_version(), mc_version)
    except ValueError:
        return False


def _write_atomic(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4)
            handle.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def sync_published_game_data(mc_version: Optional[str] = None) -> Optional[str]:
    """Fetch the published data if it is newer than the local copy. Returns the local data version."""
    current = local_data_version()
    if mc_version is not None and covers(current, mc_version):
        return current

    try:
        payloads = {name: _fetch_json(name) for name in PUBLISHED_FILES}
        published = min((p["version"] for p in payloads.values()), key=version_key)
        if current is not None and version_key(published) <= version_key(current):
            return current

        for name, payload in payloads.items():
            _write_atomic(resource_path(os.path.join(GAME_DATA_DIR, name)), payload)
        return published
    except (requests.RequestException, ValueError, OSError) as exc:
        print(f"Could not update game data from {PUBLISHED_GAME_DATA_URL}: {exc}")
        return current

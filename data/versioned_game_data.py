from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.constants import GAME_DATA_DIR
from src.resource_path import resource_path
from src.versioned_json import (
    apply_versioned_payload,
    calculate_diff,
    order_versioned_payload,
    resolve_best_version,
    sort_versions,
    update_versioned_data,
)


def _game_data_root() -> Path:
    return Path(resource_path(GAME_DATA_DIR)).resolve()


def _load_existing_payload(filename: str) -> Tuple[Optional[str], Dict[str, Any]]:
    root = _game_data_root()
    if not root.exists():
        return None, {}

    shared_path = root / filename
    if shared_path.exists():
        try:
            with shared_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None, {}

        if isinstance(data, dict) and data:
            return data.get("version"), data
        return None, {}

    versions = [entry.name for entry in root.iterdir() if entry.is_dir()]
    if not versions:
        return None, {}

    for version in reversed(sort_versions(versions)):
        path = root / version / filename
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if "version" not in data:
            continue
        return data.get("version"), data

    return None, {}


def save_versioned_json(
    version: str, filename: str, new_payload: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Update a versioned JSON payload and persist it to disk."""
    if not isinstance(new_payload, dict):
        raise TypeError("Versioned payloads must be dictionaries.")

    _, existing_payload = _load_existing_payload(filename)

    previous_version: Optional[str] = None
    if existing_payload:
        previous_version = resolve_best_version(
            [key for key in existing_payload.keys() if key != "version"], version
        )

    baseline_payload: Dict[str, Any] = {}
    if previous_version is not None:
        baseline_payload = apply_versioned_payload(existing_payload, previous_version)

    diff = calculate_diff(baseline_payload, new_payload)
    updated_payload = update_versioned_data(existing_payload, version, new_payload)
    ordered_payload = order_versioned_payload(updated_payload)

    root = _game_data_root()
    root.mkdir(parents=True, exist_ok=True)
    target_path = root / filename
    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(ordered_payload, handle, indent=4)
        handle.write("\n")

    for entry in root.iterdir():
        if entry.is_dir():
            legacy_path = entry / filename
            if legacy_path.exists():
                try:
                    legacy_path.unlink()
                except OSError:
                    pass

    return ordered_payload, diff


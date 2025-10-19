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
    target_path = root / filename
    if not target_path.exists():
        return None, {}

    with target_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        return None, {}

    version = data.get("version")
    return version if isinstance(version, str) else None, data


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

    legacy_path = root / version / filename
    if legacy_path.exists():
        try:
            legacy_path.unlink()
        except OSError:
            pass

    return ordered_payload, diff


def load_baseline_payload(filename: str, version: str) -> Dict[str, Any]:
    """Return the fully-expanded payload for the latest version prior to *version*."""
    _, existing_payload = _load_existing_payload(filename)
    if not existing_payload:
        return {}

    candidate_versions = [key for key in existing_payload.keys() if key != "version"]
    baseline_version = resolve_best_version(candidate_versions, version)
    if baseline_version is None:
        return {}

    return apply_versioned_payload(existing_payload, baseline_version)


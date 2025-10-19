from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Tuple
import re

_MISSING = object()
_VERSION_TOKEN = re.compile(r"\d+")


def version_key(version: str) -> Tuple[int, ...]:
    """Return a tuple suitable for sorting semantic Minecraft version strings."""
    tokens = [int(token) for token in _VERSION_TOKEN.findall(version)]
    if not tokens:
        raise ValueError(f"Invalid version string: {version}")
    return tuple(tokens)


def sort_versions(versions: Iterable[str]) -> List[str]:
    """Sort version strings in ascending semantic order."""
    return sorted(versions, key=version_key)


def resolve_best_version(versions: Iterable[str], target_version: str) -> Optional[str]:
    """Return the highest version from *versions* that does not exceed *target_version*."""
    target_key = version_key(target_version)
    best_version: Optional[str] = None
    best_key: Optional[Tuple[int, ...]] = None
    for candidate in versions:
        try:
            candidate_key = version_key(candidate)
        except ValueError:
            continue
        if candidate_key > target_key:
            continue
        if best_key is None or candidate_key > best_key:
            best_version = candidate
            best_key = candidate_key
    return best_version


def apply_versioned_payload(data: Dict[str, Any], target_version: str) -> Dict[str, Any]:
    """Expand versioned data up to *target_version* inclusive."""
    version_keys = [key for key in data.keys() if key != "version"]
    if not version_keys:
        return {}
    sorted_keys = sort_versions(version_keys)
    target_key = version_key(target_version)
    expanded: Dict[str, Any] = {}
    for key in sorted_keys:
        if version_key(key) > target_key:
            break
        patch = data.get(key)
        if not isinstance(patch, dict):
            continue
        for item, payload in patch.items():
            if payload is None:
                expanded.pop(item, None)
            else:
                expanded[item] = deepcopy(payload)
    return expanded


def calculate_diff(previous: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Return a diff mapping between *previous* and *new* payloads."""
    diff: Dict[str, Any] = {}
    all_keys = sorted(set(previous.keys()) | set(new.keys()))
    for key in all_keys:
        prev_value = previous.get(key, _MISSING)
        new_value = new.get(key, _MISSING)
        if prev_value is _MISSING and new_value is _MISSING:
            continue
        if prev_value == new_value:
            continue
        if new_value is _MISSING:
            diff[key] = None
        else:
            diff[key] = deepcopy(new_value)
    return diff


def update_versioned_data(
    existing_data: Dict[str, Any], version: str, new_payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge *new_payload* into *existing_data* for *version* and return the result."""
    data: Dict[str, Any] = deepcopy(existing_data) if existing_data else {}
    highest_recorded = existing_data.get("version") if existing_data else None
    data.pop(version, None)
    version_keys = [key for key in data.keys() if key != "version"]

    if not version_keys:
        data[version] = deepcopy(new_payload)
    else:
        baseline_version = resolve_best_version(version_keys, version)
        baseline_payload = {}
        if baseline_version is not None:
            baseline_payload = apply_versioned_payload(data, baseline_version)
        diff = calculate_diff(baseline_payload, new_payload)
        if diff:
            data[version] = diff
        else:
            data.pop(version, None)

    if highest_recorded is None or version_key(version) >= version_key(highest_recorded):
        data["version"] = version
    else:
        data["version"] = highest_recorded

    return data


def order_versioned_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return *data* with keys ordered for stable JSON serialisation."""
    ordered: Dict[str, Any] = {}
    if "version" in data:
        ordered["version"] = data["version"]
    version_keys = [key for key in data.keys() if key != "version"]
    for key in sorted(version_keys, key=version_key, reverse=True):
        ordered[key] = data[key]
    return ordered

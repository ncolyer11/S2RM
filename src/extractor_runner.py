from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

TARGET_FILES = (
    Path("net/minecraft/world/entity/EntityType.java"),
    Path("net/minecraft/world/level/block/Blocks.java"),
    Path("net/minecraft/world/item/Items.java"),
)

_ALLOWED_SEGMENT_CHARS = {".", "-", "_"}
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EXTRACTOR_ROOT = _PROJECT_ROOT / "extractor"
_GAME_DATA_ROOT = _EXTRACTOR_ROOT / "game_data"
_ARTIFACT_STORE_ROOT = _EXTRACTOR_ROOT / "artifact-store"


class ExtractionError(RuntimeError):
    """Raised when the extractor cannot produce the expected sources."""


def normalise_version(raw: str) -> str:
    match = re.search(r"([0-9]+(?:[._-][0-9A-Za-z]+)*)", raw.strip())
    if not match:
        raise ValueError(f"Could not parse a Minecraft version from: {raw!r}")
    return match.group(1).replace("_", ".")


def sanitise_segment(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in _ALLOWED_SEGMENT_CHARS else "_" for ch in text)


def _gradle_wrapper() -> Path:
    script = "gradlew.bat" if os.name == "nt" else "gradlew"
    path = _EXTRACTOR_ROOT / script
    if not path.exists():
        raise FileNotFoundError(f"Gradle wrapper not found at {path}.")
    return path


def _run_extractor(version: str) -> None:
    gradle_path = _gradle_wrapper()
    cmd = [
        str(gradle_path),
        "runExtractor",
        "--no-daemon",
        "--console=plain",
        f"--args={version}",
    ]
    result = subprocess.run(cmd, cwd=_EXTRACTOR_ROOT, check=False)
    if result.returncode != 0:
        raise ExtractionError(f"Extractor failed for {version} with exit code {result.returncode}.")


def _sources_root(version: str) -> Path:
    normalised = normalise_version(version)
    return _GAME_DATA_ROOT / sanitise_segment(normalised)


def _locate_source_file(root: Path, relative_path: Path) -> Path | None:
    """Return the on-disk path for a target file if it exists."""
    candidate = root / relative_path
    if candidate.exists():
        return candidate
    # New extractor pipeline copies the selected files directly under the version
    # directory, so fall back to matching by filename when the tree is flattened.
    fallback = root / relative_path.name
    if fallback.exists():
        return fallback
    return None


def ensure_extracted_sources(version: str, *, force: bool = False) -> Path:
    sources_root = _sources_root(version)
    if force or _missing_any(sources_root):
        _run_extractor(normalise_version(version))
    if _missing_any(sources_root):
        raise ExtractionError(f"Extraction finished but sources are missing for {version} at {sources_root}.")
    return sources_root


def copy_sources(version: str, destination: Path, *, overwrite: bool = True) -> None:
    sources_root = ensure_extracted_sources(version)
    destination.mkdir(parents=True, exist_ok=True)

    for relative_path in TARGET_FILES:
        source_path = _locate_source_file(sources_root, relative_path)
        if source_path is None:
            raise ExtractionError(f"Missing extracted file: {relative_path}")
        destination_path = destination / relative_path.name
        if destination_path.exists():
            if overwrite:
                destination_path.unlink()
            else:
                continue
        shutil.copy2(source_path, destination_path)
    shutil.rmtree(sources_root, ignore_errors=True)


def _missing_any(root: Path) -> bool:
    return any(_locate_source_file(root, relative_path) is None for relative_path in TARGET_FILES)


def list_missing_sources(version: str) -> Iterable[Path]:
    sources_root = _sources_root(version)
    for relative_path in TARGET_FILES:
        if _locate_source_file(sources_root, relative_path) is None:
            yield sources_root / relative_path


def cleanup_extractor_runtime(*, remove_build: bool = False) -> None:
    """Remove transient extractor artefacts to keep the repository clean."""
    for path in (_GAME_DATA_ROOT, _ARTIFACT_STORE_ROOT):
        shutil.rmtree(path, ignore_errors=True)

    if remove_build:
        build_root = _EXTRACTOR_ROOT / "build"
        shutil.rmtree(build_root, ignore_errors=True)


__all__ = [
    "ExtractionError",
    "TARGET_FILES",
    "copy_sources",
    "cleanup_extractor_runtime",
    "ensure_extracted_sources",
    "list_missing_sources",
    "normalise_version",
    "sanitise_segment",
]

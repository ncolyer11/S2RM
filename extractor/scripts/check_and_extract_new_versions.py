#!/usr/bin/env python3
"""Automates downloading and archiving sources for new Minecraft releases."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence
from urllib.error import URLError
from urllib.request import urlopen


CHECK_INTERVAL_SECONDS = int(os.environ.get("S2RM_RELEASE_CHECK_INTERVAL", "3600"))
MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
REPO_ROOT = PROJECT_ROOT.parent
DATA_GAME_DIR = REPO_ROOT / "data" / "game"


if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if os.getcwd() != str(REPO_ROOT):
    os.chdir(str(REPO_ROOT))

from data.download_game_data import download_game_data  # noqa: E402
from data.parse_mc_data import (  # noqa: E402
    cleanup_downloads,
    parse_blocks_list,
    parse_items_list,
    parse_items_stack_sizes,
)
from data.recipes_raw_mats_database_builder import generate_raw_materials_table_dict  # noqa: E402
from data.versioned_game_data import save_versioned_json  # noqa: E402
from src.constants import (  # noqa: E402
    LIMTED_STACKS_NAME,
    RAW_MATS_TABLE_NAME,
)
from src.extractor_runner import (  # noqa: E402
    TARGET_FILES,
    copy_sources,
    ensure_extracted_sources,
)


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    release_time: datetime


def parse_release_time(raw: str) -> datetime:
    cleaned = raw.strip().replace("Z", "+00:00")
    moment = datetime.fromisoformat(cleaned)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def fetch_release_manifest() -> Sequence[ReleaseInfo]:
    with urlopen(MANIFEST_URL, timeout=30) as response:
        data = json.load(response)

    releases: list[ReleaseInfo] = []
    for entry in data.get("versions", []):
        if entry.get("type") != "release":
            continue
        version = entry.get("id")
        release_time_raw = entry.get("releaseTime") or entry.get("time")
        if not version or not release_time_raw:
            continue
        try:
            release_time = parse_release_time(release_time_raw)
        except ValueError:
            logging.warning("Skipping release %s with unparseable time %s", version, release_time_raw)
            continue
        releases.append(ReleaseInfo(version, release_time))

    releases.sort(key=lambda item: item.release_time)
    return releases


def ensure_data_directory() -> None:
    DATA_GAME_DIR.mkdir(parents=True, exist_ok=True)


def processed_versions() -> set[str]:
    if not DATA_GAME_DIR.exists():
        return set()
    return {entry.name for entry in DATA_GAME_DIR.iterdir() if entry.is_dir()}


def is_version_complete(version: str) -> bool:
    target_dir = DATA_GAME_DIR / version
    if not target_dir.exists():
        return False

    for relative_path in TARGET_FILES:
        if not (target_dir / relative_path.name).exists():
            return False

    for filename in (LIMTED_STACKS_NAME, RAW_MATS_TABLE_NAME):
        if not (DATA_GAME_DIR / filename).exists():
            return False

    return True


def versions_to_process(releases: Sequence[ReleaseInfo], seen_versions: Iterable[str]) -> Sequence[ReleaseInfo]:
    release_map = {release.version: release for release in releases}
    completed = {version for version in seen_versions if version in release_map and is_version_complete(version)}
    incomplete = [release_map[version] for version in seen_versions if version in release_map and version not in completed]

    last_completed_time = max((release_map[version].release_time for version in completed), default=None)

    pending: list[ReleaseInfo] = []
    pending.extend(sorted(incomplete, key=lambda item: item.release_time))

    if last_completed_time is None:
        if releases:
            latest = releases[-1]
            if latest.version not in completed or not is_version_complete(latest.version):
                pending.append(latest)
    else:
        for release in releases:
            if release.release_time > last_completed_time:
                pending.append(release)

    unique_by_version: dict[str, ReleaseInfo] = {}
    for release in pending:
        unique_by_version[release.version] = release

    ordered_pending = sorted(unique_by_version.values(), key=lambda item: item.release_time)
    return ordered_pending


def run_extractor_for_version(version: str) -> None:
    ensure_extracted_sources(version)


def archive_files(version: str) -> None:
    destination_root = DATA_GAME_DIR / version
    copy_sources(version, destination_root)


def generate_version_payload(version: str) -> None:
    logging.info("Downloading Minecraft assets for %s", version)
    downloaded_version = download_game_data(version)
    if downloaded_version != version:
        cleanup_downloads()
        raise RuntimeError(
            f"Expected game data for {version} but received {downloaded_version}."
        )

    try:
        items_list = parse_items_list()
        blocks_list = parse_blocks_list(version)

        limited_stack_items = parse_items_stack_sizes(version)
        raw_materials_table = generate_raw_materials_table_dict(
            version,
            items_list=items_list,
            blocks_list=blocks_list,
        )

        _, limited_diff = save_versioned_json(version, LIMTED_STACKS_NAME, limited_stack_items)
        _, raw_diff = save_versioned_json(version, RAW_MATS_TABLE_NAME, raw_materials_table)

        logging.info(
            "Limited stack data updated for %s entries.", len(limited_diff)
        )
        logging.info("Raw materials data updated for %s entries.", len(raw_diff))
    finally:
        cleanup_downloads()


def process_release(release: ReleaseInfo) -> None:
    logging.info("Processing Minecraft %s", release.version)
    run_extractor_for_version(release.version)
    archive_files(release.version)
    generate_version_payload(release.version)
    logging.info("Archived and generated assets for %s", release.version)


def perform_check_cycle() -> None:
    try:
        releases = fetch_release_manifest()
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logging.error("Unable to fetch release manifest: %s", exc)
        return

    ensure_data_directory()
    seen = processed_versions()
    queue = versions_to_process(releases, seen)

    if not queue:
        logging.info("No new Minecraft release detected.")
        return

    for release in queue:
        try:
            process_release(release)
        except Exception as exc:  # noqa: BLE001
            logging.exception("Failed to process %s: %s", release.version, exc)
            break


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("Starting Minecraft release watcher.")

    try:
        while True:
            perform_check_cycle()
            logging.info("Sleeping for %s seconds before next check.", CHECK_INTERVAL_SECONDS)
            time.sleep(CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logging.info("Stopping release watcher.")


if __name__ == "__main__":
    main()

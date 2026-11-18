"""Build game data for Minecraft releases newer than the stored data.

    python -m scripts.check_new_releases [--watch]
"""
from __future__ import annotations

import argparse
import json
import logging
import time

import requests

from data.mojang_reports import MANIFEST_URL
from scripts.build_version_data import build_version
from src.game_data_sync import local_data_version
from src.versioned_json import version_key

CHECK_INTERVAL_SECONDS = 3600


def fetch_release_ids() -> list[str]:
    response = requests.get(MANIFEST_URL, timeout=30)
    response.raise_for_status()
    releases = [v for v in response.json()["versions"] if v["type"] == "release"]
    releases.sort(key=lambda v: v["releaseTime"])
    return [v["id"] for v in releases]


def pending_releases(release_ids: list[str], built_version: str | None) -> list[str]:
    """Releases newer than built_version, or just the latest if nothing is built."""
    if built_version is None:
        return release_ids[-1:]
    return [rid for rid in release_ids if version_key(rid) > version_key(built_version)]


def check_once() -> bool:
    try:
        release_ids = fetch_release_ids()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        logging.error("Unable to fetch release manifest: %s", exc)
        return False

    queue = pending_releases(release_ids, local_data_version())
    if not queue:
        logging.info("No new Minecraft release detected.")
        return True

    for version in queue:
        logging.info("Building game data for %s", version)
        try:
            build_version(version)
        except Exception:  # noqa: BLE001
            logging.exception("Failed to build %s", version)
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Build game data for new Minecraft releases.")
    parser.add_argument("--watch", action="store_true", help="Keep polling for new releases")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ok = check_once()
    while args.watch:
        time.sleep(CHECK_INTERVAL_SECONDS)
        ok = check_once()
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

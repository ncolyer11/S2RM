"""Build data/game/*.json for one Minecraft version.

    S2RM_JAVA=/path/to/java python -m scripts.build_version_data 26.3 [--no-save]
"""
from __future__ import annotations

import argparse
import logging
import shutil
import tempfile
from pathlib import Path

from data import mojang_reports as mr
from data.recipes_raw_mats_database_builder import generate_raw_materials_table_dict
from data.versioned_game_data import load_baseline_payload, save_versioned_json
from src.constants import LIMTED_STACKS_NAME, MC_DOWNLOADS_DIR, RAW_MATS_TABLE_NAME
from src.resource_path import resource_path


def build_version(version: str, work_dir: Path | None = None, *, save: bool = True) -> tuple[dict, dict]:
    """Return (raw_materials_table, limited_stack_items) for version, saving them unless save=False."""
    cleanup = work_dir is None
    work_dir = work_dir or Path(tempfile.mkdtemp(prefix="s2rm_gen_"))
    recipe_dir = Path(resource_path(MC_DOWNLOADS_DIR)) / "recipe"
    try:
        logging.info("Running Mojang data generator for %s", version)
        generated = mr.run_data_generator(version, work_dir)

        count = mr.copy_recipes(generated, recipe_dir)
        logging.info("Copied %d recipes", count)
        mr.copy_item_tags(generated, recipe_dir.parent / "tags" / "item")

        items_list = mr.parse_items_list(generated)
        blocks_list = mr.parse_blocks_list(generated)
        limited_stacks = mr.parse_items_stack_sizes(generated)

        raw_table = generate_raw_materials_table_dict(
            version, items_list=items_list, blocks_list=blocks_list
        )

        baseline = load_baseline_payload(RAW_MATS_TABLE_NAME, version)
        if baseline:
            raw_table = dict(sorted({**baseline, **raw_table}.items()))

        if save:
            _, limited_diff = save_versioned_json(version, LIMTED_STACKS_NAME, limited_stacks)
            _, raw_diff = save_versioned_json(version, RAW_MATS_TABLE_NAME, raw_table)
            logging.info("Saved %d limited-stack and %d recipe changes", len(limited_diff), len(raw_diff))
        return raw_table, limited_stacks
    finally:
        shutil.rmtree(recipe_dir.parent, ignore_errors=True)
        if cleanup:
            shutil.rmtree(work_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build game data for one Minecraft version.")
    parser.add_argument("version", help="Minecraft release id, e.g. 26.3")
    parser.add_argument("--work-dir", type=Path, help="Keep downloads/generator output here")
    parser.add_argument("--no-save", action="store_true", help="Generate but don't write data/game")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build_version(args.version, args.work_dir, save=not args.no_save)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Utility to preview the extracted Items, Blocks, and EntityType sources."""
from __future__ import annotations

import itertools
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.extractor_runner import TARGET_FILES, resolve_source_path  # noqa: E402


def preview_file(path: Path, limit: int = 20) -> None:
    print(f"\n== {path} ==")
    try:
        with path.open(encoding="utf-8") as handle:
            for line in itertools.islice(handle, limit):
                print(line.rstrip("\n"))
    except FileNotFoundError:
        print("(missing)")


def preview_sources(version: str, *, limit: int = 20) -> None:
    for relative_path in TARGET_FILES:
        preview_file(resolve_source_path(version, relative_path), limit=limit)


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if args:
        version = args[0]
    else:
        version = input("Enter Minecraft version: ")
    preview_sources(version)


if __name__ == "__main__":
    main()

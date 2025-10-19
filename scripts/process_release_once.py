from __future__ import annotations

import argparse
from datetime import datetime, timezone

from extractor.scripts.check_and_extract_new_versions import ReleaseInfo, process_release


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the extractor pipeline for a single Minecraft version.")
    parser.add_argument("version", help="Minecraft version identifier, e.g. 1.21.9")
    args = parser.parse_args()

    release = ReleaseInfo(args.version, datetime.now(timezone.utc))
    process_release(release)


if __name__ == "__main__":
    main()

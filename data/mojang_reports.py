"""Game data extraction via Mojang's own data generator (server jar --reports). Maintainer use only."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import requests

from src.constants import INVALID_BLOCKS
from src.helpers import block_to_item_name

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
_TIMEOUT = 60
_DEFAULT_STACK = 64


class DataGenError(RuntimeError):
    """Raised when the Mojang data generator cannot be run for a version."""


def _get_json(url: str) -> dict:
    response = requests.get(url, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_version_meta(version: str) -> dict:
    manifest = _get_json(MANIFEST_URL)
    for entry in manifest["versions"]:
        if entry["id"] == version:
            return _get_json(entry["url"])
    raise DataGenError(f"Minecraft version {version} not found in Mojang's manifest.")


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=_TIMEOUT) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
    partial.replace(dest)


def _java_major(java_cmd: str) -> int:
    try:
        out = subprocess.run([java_cmd, "-version"], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise DataGenError(f"Cannot run Java at {java_cmd}: {exc}") from exc
    match = re.search(r'version "(\d+)', out.stderr + out.stdout)
    if not match:
        raise DataGenError(f"Could not determine Java version from {java_cmd}.")
    return int(match.group(1))


def resolve_java(required_major: int) -> str:
    """Pick a java executable from $S2RM_JAVA, $JAVA_HOME or PATH that meets required_major."""
    candidates = [
        os.environ.get("S2RM_JAVA"),
        str(Path(os.environ["JAVA_HOME"]) / "bin" / "java") if os.environ.get("JAVA_HOME") else None,
        "java",
    ]
    seen: list[str] = []
    for candidate in filter(None, candidates):
        try:
            major = _java_major(candidate)
        except DataGenError:
            continue
        if major >= required_major:
            return candidate
        seen.append(f"{candidate} (Java {major})")
    raise DataGenError(
        f"Java {required_major}+ is required for this version. Set S2RM_JAVA to a suitable "
        f"`java` executable. Tried: {', '.join(seen) or 'none found'}."
    )


def run_data_generator(version: str, work_dir: Path) -> Path:
    """Download the server jar and run the generator. Returns the output dir."""
    meta = get_version_meta(version)
    required_java = int(meta.get("javaVersion", {}).get("majorVersion", 21))
    java_cmd = resolve_java(required_java)

    work_dir.mkdir(parents=True, exist_ok=True)
    server_jar = work_dir / f"server-{version}.jar"
    if not server_jar.exists():
        _download(meta["downloads"]["server"]["url"], server_jar)

    output = work_dir / f"generated-{version}"
    shutil.rmtree(output, ignore_errors=True)
    cmd = [
        java_cmd, "-DbundlerMainClass=net.minecraft.data.Main", "-jar", str(server_jar),
        "--reports", "--server", "--output", str(output),
    ]
    result = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, check=False, timeout=900)
    if result.returncode != 0 or not (output / "reports").exists():
        raise DataGenError(f"Data generator failed for {version}:\n{result.stderr[-2000:]}")
    return output


def _registry_names(generated: Path, registry: str) -> list[str]:
    with (generated / "reports" / "registries.json").open(encoding="utf-8") as handle:
        entries = json.load(handle)[f"minecraft:{registry}"]["entries"]
    return sorted(name.removeprefix("minecraft:") for name in entries)


def parse_items_list(generated: Path) -> list[str]:
    return _registry_names(generated, "item")


def parse_entities_list(generated: Path) -> list[str]:
    return _registry_names(generated, "entity_type")


def parse_blocks_list(generated: Path) -> list[str]:
    """Block registry names mapped to S2RM item names, minus INVALID_BLOCKS."""
    names = {block_to_item_name(name) for name in _registry_names(generated, "block")}
    return sorted(name for name in names if name not in INVALID_BLOCKS)


def _item_components(generated: Path):
    """Yield (item, components). Newer versions write one file per item, older ones a single items.json."""
    per_item = generated / "reports" / "minecraft" / "components" / "item"
    if per_item.is_dir():
        for path in per_item.glob("*.json"):
            with path.open(encoding="utf-8") as handle:
                yield path.stem, json.load(handle).get("components", {})
        return

    combined = generated / "reports" / "items.json"
    if not combined.exists():
        raise DataGenError("Data generator produced no item component report.")
    with combined.open(encoding="utf-8") as handle:
        for name, data in json.load(handle).items():
            yield name.removeprefix("minecraft:"), data.get("components", {})


def parse_items_stack_sizes(generated: Path) -> dict[str, int]:
    """Items that stack below 64. Damageable items count as 1."""
    limited: dict[str, int] = {}
    for name, components in _item_components(generated):
        size = components.get("minecraft:max_stack_size", _DEFAULT_STACK)
        if "minecraft:max_damage" in components:
            size = 1
        if size != _DEFAULT_STACK:
            limited[name] = size
    return dict(sorted(limited.items(), key=lambda kv: (kv[0], kv[1])))


def copy_recipes(generated: Path, destination: Path) -> int:
    """Copy all recipe JSONs flat into destination."""
    source = generated / "data" / "minecraft" / "recipe"
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    files = sorted(source.glob("*.json"))
    if not files:
        raise DataGenError(f"No recipes found in {source}.")
    for file in files:
        shutil.copy2(file, destination / file.name)
    return len(files)


def copy_item_tags(generated: Path, destination: Path) -> None:
    """Copy item tags so unmapped tags can be resolved by the recipe builder."""
    source = generated / "data" / "minecraft" / "tags" / "item"
    shutil.rmtree(destination, ignore_errors=True)
    shutil.copytree(source, destination)

# S2RM: Schematic to Raw Materials
Calculates a raw material list from a Litematica material list.txt, using recipe data generated from Minecraft's own data files. "Raw materials" are somewhat subjective.
<p align="center">
  <img src="https://github.com/user-attachments/assets/029e0acb-5a0e-484d-8c05-b21323cd4598" width="1000">

## Tutorial/Showcase Video
[![Watch the video](https://img.youtube.com/vi/FdPh9KoVuV8/maxresdefault.jpg)](https://youtu.be/FdPh9KoVuV8)

## About

This tool automates the process of converting Litematica material lists into the necessary raw materials for Minecraft builds. It streamlines resource gathering using recipe data generated from Minecraft's own data files and bundled with the program. Users can choose output formats (ingots or blocks), track collected materials, and save/load progress in JSON format. The application also provides a search function and quantity formatting for clarity. Please note that the definition of "raw materials" can vary.

## Key Features

* Litematica material list processing
* Bundled recipe data per Minecraft version, auto-updated on new releases
* Ingot/block output options
* Ice type selection
* Collected material tracking
* Search functionality
* Quantity formatting
* Dark/light mode
* JSON save/load

## Supported Minecraft Versions

1.21.2 through 26.3 (every release in between), with 26.3 as the default. Pick a version under `Edit` > version. Newer releases are added to this repo after they come out and the program picks them up automatically. Snapshots, joke versions and modded content are not supported.

## Usage

1.  Drag & drop or select one or multiple Litematica files (`.litematic`) and/or material lists (`.txt` or `.json`) into the program.
2.  Hit the `Process` button to compute the raw materials list.
3.  (Optional) Track collected materials, choose output/ice types, search, or save/load.

If Windows defender keeps quartinting the program like so:
![image](https://github.com/user-attachments/assets/6c1fbc6e-d67d-4017-9b70-4df2a8eab6dc)

Just follow this guide here to whitelist it: https://youtu.be/IjVWzqrBrFs?si=9bjolG5JntHAzSTD

## Updating game data (maintainers)

Recipe data comes from Mojang's official data generator, so no game code is decompiled or stored. It is built once per release and committed to `data/game/`; the program ships with it and downloads newer data from this repo.

```
S2RM_JAVA=$(which java) python -m scripts.build_version_data 26.3
python -m scripts.check_new_releases [--watch]
```

`S2RM_JAVA` must point to a Java at least as new as the release needs (a Java 25 build works for every supported version). To rebuild old versions, delete `data/game/*.json` and run `build_version_data` for each version in ascending order, since later versions are stored as diffs of earlier ones.

Builds: `build.bat` (Windows) and `build.sh` (Linux) need a conda env with the dependencies from `pyproject.toml` and PyInstaller.

## Download

[Latest Release](https://github.com/ncolyer11/S2RM/releases)

## Source

[GitHub Repository](https://github.com/ncolyer11/S2RM)

## Credits

Made by ncolyer.

## Feedback

Report issues or suggestions on GitHub or Discord.

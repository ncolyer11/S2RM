### Download S2RM v2.0.0: [<ins>Windows</ins>](https://github.com/ncolyer11/S2RM/releases/download/v2.0.0/S2RM_win.zip) | [<ins>Linux</ins>](https://github.com/ncolyer11/S2RM/releases/download/v2.0.0/S2RM_lnx.zip)
<p align="center">
  <!-- IMAGE PLACEHOLDER: screenshot of the main S2RM window with a schematic loaded, showing the input items table and raw materials table side by side (the same hero shot as the last release, ideally with the version showing 26.3) -->
  <img src="PLACEHOLDER_MAIN_WINDOW" width="850">
</p>

### TL;DR

S2RM no longer needs to decompile Minecraft on your machine, or scrape a third-party repo of decompiled code, to know what's in the game. The raw materials table is now built from **Mojang's own official data generator**, and the program ships with the data for **Minecraft 1.21.2 all the way up to 26.3** already bundled. New Minecraft versions get picked up automatically once I publish their data. Oh and the Linux build actually works properly now, and the zips are a lot smaller.

### What Changed

* **Why this update exists:** Previously S2RM downloaded the Minecraft jar, decompiled it, and then pulled block and entity names from a third-party GitHub repo of decompiled game code. That repo got taken down, which broke S2RM for every new Minecraft version (#4) as well as the `iron_chain` rename (#6). Rather than patch around it again, I've removed the dependency completely, so there's no decompiling, no third-party repos, and no Mojang source code stored or published anywhere in S2RM anymore.

* **The New Data Generator:** Minecraft's server jar has a built-in data generator (`java -jar server.jar --reports --server`) that spits out every registry, every item's components and every single recipe as plain JSON. This is exactly the data S2RM needs, so now:
  1. I run the generator once for each new Minecraft release (`scripts/check_new_releases.py`, or `scripts/build_version_data.py` for a single version).
  2. It reads the generated blocks, items, entities and recipes, and works out the stack sizes (`max_stack_size`, or 1 for anything damageable) and the raw materials cost of everything in the game.
  3. Only two small versioned json files get published to `data/game/`: the raw materials table and the limited stack items list. Each one stores only what *changed* in each version, so they stay tiny even with 15 versions in them.
  4. Your copy of S2RM ships with those files bundled in, and when a newer set is published to the repo it downloads just those two files. You never have to download, decompile or process any game files yourself.

  <!-- IMAGE PLACEHOLDER: screenshot of the terminal/console window showing the "new Minecraft version available, downloading game data" messages after clicking 'yes' on the update prompt -->

  If a download fails (offline, GitHub being GitHub, etc.) the data you already have is left alone, files are written atomically so a half finished download can't corrupt anything.

* **Minecraft 1.21.2 to 26.3 Support:** 15 releases are supported, each with its own recipes and stack sizes: 1.21.2, 1.21.3, 1.21.4, 1.21.5, 1.21.6, 1.21.7, 1.21.8, 1.21.9, 1.21.10, 1.21.11, 26.1, 26.1.1, 26.1.2, 26.2 and 26.3.
  <!-- IMAGE PLACEHOLDER: screenshot of the Version Selection dialog open, showing the list of supported versions with 26.3 selected -->
  - 26.3 is the default version now
  - Entering a version older than 1.21.2 (or newer than I've published data for) falls back to the newest version and tells you it did
  - New Minecraft versions only get offered in the update prompt once their data has actually been published, so you won't be told to update to something that isn't there yet
  - Snapshots and joke versions aren't supported at the moment, so `snap`/`snapshot` won't give you anything useful for now

* **Reliable Linux Port:** The Linux build has been reworked so it behaves the same as the Windows one:
  - `build.sh` (and `build.bat`) bundle the game data json files directly instead of the old per-version folder juggling, so a fresh build works on the first try
  - No Java, decompiler, or git repos needed on the end user's machine anymore, just unzip and run
  - Files are now located properly relative to the program whether you're running from source or the packaged build
  - I've also done a bunch of cleanup in how the Linux build is put together (see file sizes below)

* **Way Smaller Downloads:** I finally figured out what I was doing wrong with PyInstaller (sorry for the whining last time!). The build was pulling in matplotlib, networkx, PIL and a pile of Qt modules (software OpenGL, PDF, QML, SVG etc.) that S2RM never actually uses. These are all excluded now and the Linux build is stripped.
  - Windows zip: ~71 MB → ~38 MB
  - Linux zip: ~160 MB → **[FILL IN after building on Linux]**

  <!-- IMAGE PLACEHOLDER: screenshot of the two zip files in a file explorer showing their sizes, or just a before/after size comparison -->

* **Removed:** The GitCraft extractor, all checked-in decompiled `.java` files, and the code that only existed to parse them. Also removed the unused block and item texture files, and the dead "Clear Saved MC Versions" menu item.

### Minor Tweaks
   - Bundle recipes are now supported properly, including dyeing bundles (bundles used to be a bit broken as they were being treated like shulker boxes)
   - Concrete stairs and slabs now cost their actual concrete ingredients (and so on down to the raw materials) instead of being left as is
   - Coloured candle cakes now include the dye of their candle in their cost
   - `iron_chain` and `copper_chain` are recognised, and the legacy `chain` name still works so old schematics don't break (#6)
   - Recipes that omit `result.count` and tags that weren't mapped yet (`#poplar_logs`, `#mushrooms`, `#metal_nuggets`) are now handled, so new 26.x recipes parse correctly
   - Unmapped item tags now fall back to the tags generated by the data generator, with a warning in the console instead of silently going missing
   - Stack sizes now come straight from the game instead of being parsed out of source code
   - Versions that had no recipe or stack size changes still get an entry, so every release shows up in the version dialog
   - The update check now compares versions properly (newer than) rather than just "different to"
   - `requests` is now a properly declared dependency
   - README expanded with supported versions and maintainer notes
   - A whole lot of dev-side cleanup (removed old parsers/runners, tidied the config code, new `scripts/` folder for generating version data)

### A Few Bug Fixes
   - S2RM broke on every Minecraft version released after the third-party code repo got taken down (#4)
   - `iron_chain` and `copper_chain` weren't resolving (#6)
   - Bundle dyeing was costing a whole shulker box instead of a bundle
   - Concrete stairs and slabs weren't resolving concrete down to its powder recipe
   - Coloured candle cakes were missing the dye from their candle
   - A bogus "package" stack size was getting picked up from the old parsing
   - Which recipe won when there were duplicates depended on the order your filesystem read the files in, so results could differ between machines (now sorted)
   - Saved material table json files from before json v8 wouldn't open properly: the tv/tt data wasn't being rebuilt correctly, exclude values were getting overwritten by their formatted text, and the validation was reading the old layout
   - Unversioned or corrupt saved json files threw an exception instead of showing the usual warning
   - A false "new version of S2RM available" prompt on startup (the 2 in "S2RM" was being read as part of the version number, so v1.3.4 looked like v2.1.3.4 and beat v2.0.0)
   - S2RM crashing on startup if the new release check failed (GitHub's unauthenticated API rate limit, an outage, or a hanging connection). It now times out after 10 seconds and just skips the check
   - A failed game data download could clobber the data you already had, it now keeps what's stored
   - File paths not resolving correctly when running S2RM from source instead of the packaged build
   - Pale oak recipes are missing in **1.21.2 and 1.21.3** (known limitation: the data generator leaves out recipes behind experimental feature flags in those versions, nothing I can do about it right now)

**Windows Defender Workaround**: For those struggling to get this to run on Windows due to Windows Defender, see how to whitelist the program in the README.md.

### Downloads
- [**Windows**](https://github.com/ncolyer11/S2RM/releases/download/v2.0.0/S2RM_win.zip)
- [**Linux**](https://github.com/ncolyer11/S2RM/releases/download/v2.0.0/S2RM_lnx.zip)

Mods (#1) are not covered by this release.

### Feedback and Contributions

I welcome any feedback so please report any issues or suggestions on this release or contact me on discord.
E.g. if anyone wants to turn this into a website feel free, ik .exe's can be scary.

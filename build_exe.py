import os
import sys
import subprocess

# Define important paths
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_SCRIPT = "S2RM_frontend.py"
DIST_DIR = os.path.join(PROJECT_DIR, "dist")

# Files and directories that should be included in the .exe bundle
DATA_FILES = ['limited_stacks.json', 'icon.ico','raw_materials_table.json']
OTHER_FILES = ["constants.py", "S2RM_backend.py", "helpers.py"]
print(f"Using data files: {DATA_FILES}")

# Detect OS for correct PyInstaller format
if sys.platform == "win32":
    ADD_DATA_FLAG = ";."
else:
    ADD_DATA_FLAG = ":."

# Construct --add-data arguments for .json and other files
add_data_args = []
for file in DATA_FILES + OTHER_FILES:
    file_path = os.path.join(PROJECT_DIR, file)
    if os.path.exists(file_path):
        add_data_args.extend(["--add-data", f"{file}{ADD_DATA_FLAG}"])

# Construct PyInstaller command (with --noconsole to hide terminal output)
pyinstaller_cmd = [
    "pyinstaller",  # Call pyinstaller directly
    "--onefile",  # Export as one file
    "--icon", "icon.ico",  # Specify icon
    "--add-data", f"icon.ico;icon",  # Ensure the icon is bundled
    "--hidden-import", "PySide6",
    "--distpath", DIST_DIR,  # Specify output directory
    "--name", "S2RM",
    "--noconsole",  # Hide the terminal window
    FRONTEND_SCRIPT
] + add_data_args

# Run PyInstaller
print("\n🚀 Building .exe with PyInstaller...")
build_result = subprocess.run(pyinstaller_cmd)

# Check the results
if build_result.returncode == 0:
    print(f"\n✅ Build complete! Executable and resources are in: {DIST_DIR}")
else:
    print("\n❌ Build failed. Check PyInstaller logs.")

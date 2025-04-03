#!/bin/bash

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed or not in the PATH. Please install Conda and try again."
    exit 1
fi

# Function to find the highest Minecraft version
find_highest_version() {
    local game_dir="data/game"
    local versions=()
    local snapshots=()
    local other_versions=()
    
    # Collect all version directories
    for dir in "$game_dir"/*; do
        if [ -d "$dir" ]; then
            version=$(basename "$dir")
            
            # Check if it's a regular version (like 1.21.5)
            if [[ $version =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
                versions+=("$version")
            # Check if it's a snapshot
            elif [[ $version =~ ^[0-9]+w[0-9]+[a-z]$ ]] || [[ $version == *"snapshot"* ]]; then
                snapshots+=("$version")
            # Other versions (beta, etc.)
            else
                other_versions+=("$version")
            fi
        fi
    done
    
    # Sort versions in descending order
    if [ ${#versions[@]} -gt 0 ]; then
        # Sort regular versions and return the highest
        IFS=$'\n' sorted_versions=($(sort -t. -k1,1nr -k2,2nr -k3,3nr <<<"${versions[*]}"))
        unset IFS
        echo "${sorted_versions[0]}"
        return
    fi
    
    # If no regular versions, check snapshots
    if [ ${#snapshots[@]} -gt 0 ]; then
        # For snapshots, we'll do a simple string sort which should work for the format described
        IFS=$'\n' sorted_snapshots=($(sort -r <<<"${snapshots[*]}"))
        unset IFS
        echo "${sorted_snapshots[0]}"
        return
    fi
    
    # If no regular or snapshot versions, return the first other version
    if [ ${#other_versions[@]} -gt 0 ]; then
        echo "${other_versions[0]}"
        return
    fi
    
    # If no versions found
    echo "No Minecraft versions found in $game_dir"
    exit 1
}

# Activate the Anaconda environment
source $(conda info --base)/etc/profile.d/conda.sh
conda activate S2RM

# Check if the environment activation was successful
if [ $? -ne 0 ]; then
    echo "Failed to activate the Conda environment 'S2RM'. Please ensure it exists and try again."
    exit 1
fi

# Find the highest Minecraft version
selected_version=$(find_highest_version)
echo "Selected Minecraft version: $selected_version"

# Build with PyInstaller
python -m PyInstaller \
    --name "S2RM" \
    --windowed \
    --add-data "src/*.py:src" \
    --add-data "src/*.json:src" \
    --add-data "data/*.py:data" \
    --add-data "data/game/$selected_version/limited_stack_items.json:data/game/$selected_version" \
    --add-data "data/game/$selected_version/raw_materials_table.json:data/game/$selected_version" \
    --distpath "." \
    --noconfirm \
    main.py

# Check if PyInstaller was successful
if [ $? -ne 0 ]; then
    echo "PyInstaller build failed. Exiting."
    exit 1
fi

# Compress the output folder
zip -r "S2RM/S2RM.zip" "S2RM"

# Check if compression was successful
if [ $? -ne 0 ]; then
    echo "Compression failed. Exiting."
    exit 1
fi

echo "Build and compression completed successfully."

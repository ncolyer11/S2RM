#!/bin/bash

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed or not in the PATH. Please install Conda and try again."
    exit 1
fi

# Activate the Anaconda environment
source $(conda info --base)/etc/profile.d/conda.sh
conda activate S2RM

# Check if the environment activation was successful
if [ $? -ne 0 ]; then
    echo "Failed to activate the Conda environment 'S2RM'. Please ensure it exists and try again."
    exit 1
fi

# Build with PyInstaller
python -m PyInstaller \
    --name "S2RM" \
    --windowed \
    --add-data "src:src" \
    --add-data "data/*.json:data" \
    --add-data "data/*.py:data" \
    --add-data "data/game:data/game" \
    --icon "src/icon.ico" \
    --distpath "." \
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

#!/bin/bash

S2_APP_ID="lnx"

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

# Delete previous zip build folder
if [ -d "S2RM_${S2_APP_ID}" ]; then
    rm -rf "S2RM_${S2_APP_ID}"
fi

# Build with PyInstaller --windowed to remove terminal
python -m PyInstaller \
    --name "S2RM_$S2_APP_ID" \
    --add-data "src/*.py:src" \
    --add-data "src/*.json:src" \
    --add-data "src/icon.ico:src" \
    --add-data "data/*.py:data" \
    --add-data "data/game/*.json:data/game" \
    --distpath "." \
    --noconfirm \
    main.py

# Check if PyInstaller was successful
if [ $? -ne 0 ]; then
    echo "PyInstaller build failed. Exiting."
    exit 1
fi

# Compress the output folder and rename the zip using the app identifier
zip -r "S2RM_${S2_APP_ID}.zip" "S2RM_${S2_APP_ID}"

# Check if compression was successful
if [ $? -ne 0 ]; then
    echo "Compression failed. Exiting."
    exit 1
fi

mv "S2RM_${S2_APP_ID}.zip" "S2RM_lnx/"

echo "Build and compression completed successfully."

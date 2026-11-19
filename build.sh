#!/bin/bash

S2_APP_ID="lnx"
# Conda env to build in (override with: S2RM_BUILD_ENV=myenv ./build.sh)
S2RM_BUILD_ENV="${S2RM_BUILD_ENV:-s2rm-build}"

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed or not in the PATH. Please install Conda and try again."
    exit 1
fi

# Activate the Anaconda environment
source $(conda info --base)/etc/profile.d/conda.sh
conda activate "$S2RM_BUILD_ENV"

# Check if the environment activation was successful
if [ $? -ne 0 ]; then
    echo "Failed to activate the Conda environment '$S2RM_BUILD_ENV'. Please ensure it exists and try again."
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
    --noupx \
    --strip \
    --exclude-module matplotlib \
    --exclude-module zstandard \
    --exclude-module cryptography \
    --exclude-module PySide6.QtVirtualKeyboard \
    --exclude-module PIL \
    --exclude-module contourpy \
    --exclude-module kiwisolver \
    --exclude-module networkx \
    --exclude-module tkinter \
    --exclude-module setuptools \
    --exclude-module pkg_resources \
    --exclude-module wheel \
    --exclude-module PySide6.QtQuick \
    --exclude-module PySide6.QtQml \
    --exclude-module PySide6.QtQuickWidgets \
    --exclude-module PySide6.QtPdf \
    --exclude-module PySide6.QtPdfWidgets \
    --exclude-module PySide6.QtOpenGL \
    --exclude-module PySide6.QtOpenGLWidgets \
    --exclude-module PySide6.QtNetwork \
    --exclude-module PySide6.QtSvg \
    --exclude-module PySide6.QtSvgWidgets \
    --exclude-module PySide6.QtWebEngineCore \
    --exclude-module PySide6.QtMultimedia \
    --exclude-module PySide6.Qt3DCore \
    --exclude-module PySide6.QtCharts \
    --exclude-module PySide6.QtDataVisualization \
    --exclude-module PySide6.QtDesigner \
    --exclude-module PySide6.QtHelp \
    --exclude-module PySide6.QtSql \
    --exclude-module PySide6.QtTest \
    main.py

# Check if PyInstaller was successful
if [ $? -ne 0 ]; then
    echo "PyInstaller build failed. Exiting."
    exit 1
fi

# Drop unused Qt pieces that PyInstaller still collects
find "S2RM_${S2_APP_ID}" \( -name "libQt6Pdf*" -o -name "libQt6Quick*" -o -name "libQt6Qml*" -o -name "libQt6VirtualKeyboard*" \) -delete 2>/dev/null
rm -rf "S2RM_${S2_APP_ID}/_internal/PySide6/Qt/translations" "S2RM_${S2_APP_ID}/_internal/PySide6/Qt/qml" 2>/dev/null

# Compress the output folder and rename the zip using the app identifier
zip -r -9 "S2RM_${S2_APP_ID}.zip" "S2RM_${S2_APP_ID}"

# Check if compression was successful
if [ $? -ne 0 ]; then
    echo "Compression failed. Exiting."
    exit 1
fi

mv "S2RM_${S2_APP_ID}.zip" "S2RM_lnx/"

echo "Build and compression completed successfully."

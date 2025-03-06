@echo off

:: Check if conda is available
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo "Conda is not installed or not in the PATH. Please install Conda and try again."
    exit /b 1
)

:: Activate the Anaconda environment
CALL conda activate s2rm

:: Check if the environment activation was successful
if %errorlevel% neq 0 (
    echo "Failed to activate the Conda environment 's2rm'. Please ensure it exists and try again."
    exit /b 1
)

:: Build with PyInstaller
pyinstaller ^
--add-data "icon.ico;icon" ^
--add-data "limited_stacks.json;." ^
--add-data "icon.ico;." ^
--add-data "raw_materials_table.json;." ^
--add-data "constants.py;." ^
--add-data "S2RM_backend.py;." ^
--add-data "helpers.py;." ^
--icon=icon.ico ^
--name "S2RM" ^
--windowed ^
main.py

:: Check if PyInstaller was successful
if %errorlevel% neq 0 (
    echo "PyInstaller build failed. Exiting."
    exit /b 1
)

:: Compress the output folder
powershell Compress-Archive -Path 'dist\\S2RM\\*' -Force -DestinationPath 'S2RM.zip'

:: Check if compression was successful
if %errorlevel% neq 0 (
    echo "Compression failed. Exiting."
    exit /b 1
)

echo "Build and compression completed successfully."

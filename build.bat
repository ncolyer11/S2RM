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
    --name "S2RM" ^
    --windowed ^
    --add-data "src;src" ^
    --add-data "data/*.json;data" ^
    --add-data "data/*.py;data" ^
    --add-data "data/game;data/game" ^
    --icon "src\icon.ico" ^
    --distpath "." ^
main.py

:: Check if PyInstaller was successful
if %errorlevel% neq 0 (
    echo "PyInstaller build failed. Exiting."
    exit /b 1
)

:: Compress the output folder
powershell Compress-Archive -Path "S2RM\*" -Force -DestinationPath "S2RM\S2RM.zip"

:: Check if compression was successful
if %errorlevel% neq 0 (
    echo "Compression failed. Exiting."
    exit /b 1
)

echo "Build and compression completed successfully."

@echo off
:: Define global variable for app name
set "APP_NAME=S2RM_win"

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
    --name "%APP_NAME%" ^
    --add-data "src\*.py;src" ^
    --add-data "src\*.json;src" ^
    --add-data "src\icon.ico;src" ^
    --add-data "data\*.py;data" ^
    --add-data "data\game\*.json;data\game" ^
    --icon "src\icon.ico" ^
    --distpath "." ^
    --noconfirm ^
    main.py

:: Check if PyInstaller was successful
if %errorlevel% neq 0 (
    echo "PyInstaller build failed. Exiting."
    exit /b 1
)

:: Remove any existing zip file
if exist "%APP_NAME%\%APP_NAME%.zip" (
    echo Deleting existing zip file...
    del /f /q "%APP_NAME%\%APP_NAME%.zip" 2>nul
    if %errorlevel% neq 0 (
        echo Failed to delete existing zip file. Continuing anyway...
    )
)

:: Compress the output folder using PowerShell
echo Compressing the output folder...
powershell -Command "Compress-Archive -Path '%APP_NAME%\*' -Force -DestinationPath '%APP_NAME%\%APP_NAME%.zip'"

:: Check if compression was successful
if %errorlevel% neq 0 (
    echo "Compression failed. Exiting."
    exit /b 1
)

echo "Build and compression completed successfully."
exit /b 0

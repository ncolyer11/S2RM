@echo off
:: Define global variable for app name
set "APP_NAME=S2RM_win"

:: Check if conda is available
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo "Conda is not installed or not in the PATH. Please install Conda and try again."
    exit /b 1
)

:: Function to find the highest Minecraft version
setlocal EnableDelayedExpansion
set "game_dir=data\game"
set "highest_regular="
set "highest_snapshot="
set "first_other="

:: Collect all version directories
for /d %%v in ("%game_dir%\*") do (
    set "version=%%~nxv"
    
    :: Check if it's a regular version (like 1.21.5)
    echo !version! | findstr /r "^[0-9][0-9]*\.[0-9][0-9]*\(\.[0-9][0-9]*\)*$" >nul
    if !errorlevel! equ 0 (
        if "!highest_regular!"=="" (
            set "highest_regular=!version!"
        ) else (
            :: Compare versions (this is simplified and may not work for all cases)
            call :compare_versions "!version!" "!highest_regular!"
            if !errorlevel! equ 1 (
                set "highest_regular=!version!"
            )
        )
    ) else (
        :: Check if it's a snapshot
        echo !version! | findstr /r "^[0-9][0-9]*w[0-9][0-9]*[a-z]$" >nul
        if !errorlevel! equ 0 (
            if "!highest_snapshot!"=="" (
                set "highest_snapshot=!version!"
            ) else (
                :: For snapshots, just use string comparison (may not be perfect)
                if "!version!" gtr "!highest_snapshot!" (
                    set "highest_snapshot=!version!"
                )
            )
        ) else (
            :: Other versions
            if "!first_other!"=="" (
                set "first_other=!version!"
            )
        )
    )
)

:: Determine which version to use
set "selected_version="
if not "!highest_regular!"=="" (
    set "selected_version=!highest_regular!"
) else if not "!highest_snapshot!"=="" (
    set "selected_version=!highest_snapshot!"
) else if not "!first_other!"=="" (
    set "selected_version=!first_other!"
) else (
    echo "No Minecraft versions found in %game_dir%"
    exit /b 1
)

echo Selected Minecraft version: !selected_version!

:: Activate the Anaconda environment
CALL conda activate s2rm

:: Check if the environment activation was successful
if %errorlevel% neq 0 (
    echo "Failed to activate the Conda environment 's2rm'. Please ensure it exists and try again."
    exit /b 1
)

:: Build with PyInstaller
pyinstaller ^
    --name "!APP_NAME!" ^
    --add-data "src\*.py;src" ^
    --add-data "src\*.json;src" ^
    --add-data "src\icon.ico;src" ^
    --add-data "data\*.py;data" ^
    --add-data "data\game\!selected_version!\limited_stack_items.json;data\game\!selected_version!" ^
    --add-data "data\game\!selected_version!\raw_materials_table.json;data\game\!selected_version!" ^
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
if exist "!APP_NAME!\!APP_NAME!.zip" (
    echo Deleting existing zip file...
    del /f /q "!APP_NAME!\!APP_NAME!.zip" 2>nul
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

:compare_versions
:: Compare two version strings
:: Returns 1 if first version is higher, 0 otherwise
:: This is a simple implementation and may not handle all cases
setlocal EnableDelayedExpansion
set "v1=%~1"
set "v2=%~2"

:: Split versions into components
for /f "tokens=1,2,3 delims=." %%a in ("%v1%") do (
    set "v1_major=%%a"
    set "v1_minor=%%b"
    set "v1_patch=%%c"
)
if "!v1_patch!"=="" set "v1_patch=0"

for /f "tokens=1,2,3 delims=." %%a in ("%v2%") do (
    set "v2_major=%%a"
    set "v2_minor=%%b"
    set "v2_patch=%%c"
)
if "!v2_patch!"=="" set "v2_patch=0"

:: Compare major version
if !v1_major! gtr !v2_major! (
    endlocal & exit /b 1
) else if !v1_major! lss !v2_major! (
    endlocal & exit /b 0
)

:: Compare minor version
if !v1_minor! gtr !v2_minor! (
    endlocal & exit /b 1
) else if !v1_minor! lss !v2_minor! (
    endlocal & exit /b 0
)

:: Compare patch version
if !v1_patch! gtr !v2_patch! (
    endlocal & exit /b 1
) else (
    endlocal & exit /b 0
)

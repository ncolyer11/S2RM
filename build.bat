@echo off
:: Define global variable for app name
set "APP_NAME=S2RM_win"
:: Conda env to build in (override with: set S2RM_BUILD_ENV=myenv)
if not defined S2RM_BUILD_ENV set "S2RM_BUILD_ENV=s2rm-build"

:: Check if conda is available
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo "Conda is not installed or not in the PATH. Please install Conda and try again."
    exit /b 1
)

:: Activate the Anaconda environment
CALL conda activate %S2RM_BUILD_ENV%

:: Check if the environment activation was successful
if %errorlevel% neq 0 (
    echo "Failed to activate the Conda environment '%S2RM_BUILD_ENV%'. Please ensure it exists and try again."
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
    --noupx ^
    --exclude-module matplotlib ^
    --exclude-module zstandard ^
    --exclude-module cryptography ^
    --exclude-module PySide6.QtVirtualKeyboard ^
    --exclude-module PIL ^
    --exclude-module contourpy ^
    --exclude-module kiwisolver ^
    --exclude-module networkx ^
    --exclude-module tkinter ^
    --exclude-module setuptools ^
    --exclude-module pkg_resources ^
    --exclude-module wheel ^
    --exclude-module PySide6.QtQuick ^
    --exclude-module PySide6.QtQml ^
    --exclude-module PySide6.QtQuickWidgets ^
    --exclude-module PySide6.QtPdf ^
    --exclude-module PySide6.QtPdfWidgets ^
    --exclude-module PySide6.QtOpenGL ^
    --exclude-module PySide6.QtOpenGLWidgets ^
    --exclude-module PySide6.QtNetwork ^
    --exclude-module PySide6.QtSvg ^
    --exclude-module PySide6.QtSvgWidgets ^
    --exclude-module PySide6.QtWebEngineCore ^
    --exclude-module PySide6.QtMultimedia ^
    --exclude-module PySide6.Qt3DCore ^
    --exclude-module PySide6.QtCharts ^
    --exclude-module PySide6.QtDataVisualization ^
    --exclude-module PySide6.QtDesigner ^
    --exclude-module PySide6.QtHelp ^
    --exclude-module PySide6.QtSql ^
    --exclude-module PySide6.QtTest ^
    main.py

:: Check if PyInstaller was successful
if %errorlevel% neq 0 (
    echo "PyInstaller build failed. Exiting."
    exit /b 1
)

:: Drop Qt pieces a QtWidgets-only app never loads (software OpenGL, PDF, QML/Quick, SVG, network, virtual keyboard)
del /f /q "%APP_NAME%\_internal\PySide6\opengl32sw.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6Pdf.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6Quick.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6Qml.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6QmlMeta.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6QmlModels.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6QmlWorkerScript.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6VirtualKeyboard.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6Network.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6Svg.dll" 2>nul
del /f /q "%APP_NAME%\_internal\PySide6\Qt6OpenGL.dll" 2>nul
if exist "%APP_NAME%\_internal\PySide6\translations" rmdir /s /q "%APP_NAME%\_internal\PySide6\translations"

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

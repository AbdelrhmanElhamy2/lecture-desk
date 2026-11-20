@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Lecture Desk - Engineering Study Suite
cd /d "%~dp0"

:: ============================================================================
:: Lecture Desk - 1-Click Installer & Launcher for Windows
:: - Automatically finds Python 3.10+ (even if not added to PATH)
:: - Offers 1-key automatic Python installation via Windows winget if missing
:: - Creates an isolated .venv and installs required packages on first run
:: - Adds a "Lecture Desk" icon to your Desktop
:: - Opens Lecture Desk in a clean desktop app window
:: ============================================================================

set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_PYW=%VENV_DIR%\Scripts\pythonw.exe"
set "STAMP_FILE=%VENV_DIR%\.deps_installed"

:: --- FAST PATH: Already installed? Launch immediately! ---
if exist "%VENV_PY%" (
    if exist "%STAMP_FILE%" (
        "%VENV_PY%" -c "import fastapi, google.genai, reportlab, matplotlib" >nul 2>&1
        if !errorlevel! equ 0 (
            goto :launch_app
        )
    )
)

echo.
echo ========================================================================
echo          Lecture Desk - Engineering Study Suite (First-Time Setup)
echo ========================================================================
echo.
echo Checking your computer for Python 3.10 or newer...

call :find_python
if not defined PYTHON_EXE (
    echo.
    echo [!] Python 3.10 or newer was not found on this computer.
    echo     Lecture Desk needs Python to run locally on your PC.
    echo.
    where winget >nul 2>&1
    if !errorlevel! equ 0 (
        echo Good news: Windows can install Python 3.12 for you automatically!
        echo.
        set /p INSTALL_PY="Install Python 3.12 automatically now? (Y/N, press Enter for Yes): "
        if /i "!INSTALL_PY!"=="" set "INSTALL_PY=Y"
        if /i "!INSTALL_PY!"=="Y" (
            echo.
            echo Installing Python 3.12 via Windows Package Manager ^(winget^)...
            echo Please wait 1-2 minutes...
            winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
            echo.
            echo Checking for newly installed Python...
            call :find_python
        )
    )
)

if not defined PYTHON_EXE (
    echo.
    echo ========================================================================
    echo   HOW TO INSTALL PYTHON ^(takes 1 minute^):
    echo   1. We will open the official Python download page in your browser.
    echo   2. Click "Download Python", run the installer, and CHECK the box:
    echo         [x] Add python.exe to PATH
    echo   3. After it finishes, double-click "Start_Lecture_Desk.bat" again!
    echo ========================================================================
    echo.
    start "" "https://www.python.org/downloads/"
    pause
    exit /b 1
)

echo [OK] Found Python: !PYTHON_VER!
echo.

:: --- Step 1/3: Create isolated virtual environment ---
if not exist "%VENV_PY%" (
    echo [1/3] Creating an isolated app folder ^(.venv^)...
    "!PYTHON_EXE!" !PYTHON_ARGS! -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo.
        echo [ERROR] Could not create the app environment ^(.venv^).
        echo Please make sure this folder is not inside a read-only location ^(like a ZIP preview^).
        echo Tip: Right-click the downloaded ZIP file and choose "Extract All..." first.
        echo.
        pause
        exit /b 1
    )
) else (
    echo [1/3] App environment ^(.venv^) already exists.
)

:: --- Step 2/3: Install packages ---
echo.
echo [2/3] Installing Lecture Desk packages ^(first time only, about 1-2 minutes^)...
echo       Please keep this window open until it finishes.
echo.
"%VENV_PY%" -m pip install --upgrade pip --quiet >nul 2>&1
"%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Package installation failed.
    echo Please check your internet connection and double-click "Start_Lecture_Desk.bat" again.
    echo.
    pause
    exit /b 1
)

echo installed > "%STAMP_FILE%"

:: --- Step 3/3: Create Desktop Shortcut ---
echo.
echo [3/3] Adding "Lecture Desk" shortcut to your Desktop...
"%VENV_PY%" "%~dp0create_desktop_shortcut.py" >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] Desktop shortcut created! Next time you can open Lecture Desk right from your Desktop.
) else (
    echo [Note] Could not create Desktop shortcut automatically. You can always open Start_Lecture_Desk.bat.
)

echo.
echo ========================================================================
echo   Setup complete! Opening Lecture Desk now...
echo   Tip: Click "Settings" at top-right to paste your free Gemini API key,
echo        or click "Try Sample Lecture" to explore right away!
echo ========================================================================
echo.
timeout /t 2 /nobreak >nul

:launch_app
if exist "%VENV_PYW%" (
    start "" "%VENV_PYW%" "%~dp0launcher.py"
) else (
    start "" "%VENV_PY%" "%~dp0launcher.py"
)
exit /b 0

:: ============================================================================
:: Helper: Detect a real Python 3.10+ interpreter (ignores Windows Store stubs)
:: ============================================================================
:find_python
set "PYTHON_EXE="
set "PYTHON_ARGS="
set "PYTHON_VER="

:: 1. Try Windows py launcher first
py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
    for /f "delims=" %%v in ('py -3 --version 2^>^&1') do set "PYTHON_VER=%%v"
    exit /b 0
)

:: 2. Try python on PATH
python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=python"
    for /f "delims=" %%v in ('python --version 2^>^&1') do set "PYTHON_VER=%%v"
    exit /b 0
)

:: 3. Try python3 on PATH
python3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_EXE=python3"
    for /f "delims=" %%v in ('python3 --version 2^>^&1') do set "PYTHON_VER=%%v"
    exit /b 0
)

:: 4. Scan standard user & system install directories (even if user forgot "Add to PATH")
for %%V in (314 313 312 311 310) do (
    for %%D in ("%LOCALAPPDATA%\Programs\Python\Python%%V" "C:\Program Files\Python%%V" "C:\Python%%V") do (
        if exist "%%~D\python.exe" (
            "%%~D\python.exe" -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PYTHON_EXE=%%~D\python.exe"
                for /f "delims=" %%v in ('"%%~D\python.exe" --version 2^>^&1') do set "PYTHON_VER=%%v"
                exit /b 0
            )
        )
    )
)
exit /b 1

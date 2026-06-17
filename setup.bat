@echo off
title Discord Nuke Tool - Setup & Run
color 0A
echo ================================================
echo       Discord Nuke Tool
echo     Python 3.12+ Required
echo ================================================
echo.
echo [1] Checking Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [Error] Python is not installed or not in PATH!
    echo Please install Python 3.12 from https://python.org
    echo.
    pause
    exit /b 1
)
python --version
echo.
echo [2] Upgrading pip...
python -m pip install --upgrade pip -q
echo [DONE] pip upgraded
echo.
echo [3] Installing required packages
echo Installing discord.py, aiohttp, pystyle, colorama...
pip install discord.py aiohttp pystyle colorama --quiet
if errorlevel 1 (
    echo [WARNING] Some packages failed, retrying with no cache...
    pip install discord.py aiohttp pystyle colorama --quiet --no-cache-dir
)
echo.
echo [4] Verifying installations
python -c "import discord, aiohttp, pystyle, colorama; print('[OK] All packages installed successfully!')" 2>nul
if errorlevel 1 (
    echo [Failed] Some packages failed to install.
    echo Try running as Administrator or install manually.
    echo.
    pause
    exit /b 1
)
echo.
echo ================================================
echo     Setup Complete! Launching tool
echo ================================================
echo.
echo [5] Running main.py
echo.
python main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to run main.py
    echo Make sure main.py is in the same folder as this .bat file
    echo.
    pause
)
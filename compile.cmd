@echo off
title %cd%

where poetry >nul 2>&1
if errorlevel 1 (
    echo Poetry is not installed. Run: pipx install poetry
    pause
    exit /b 1
)

poetry install --with dev --no-root --no-interaction
if errorlevel 1 exit /b 1

poetry run pyinstaller --onefile --windowed --clean --name main app.py


echo done


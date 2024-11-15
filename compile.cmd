@echo off
title %cd%

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate

if not exist .venv\Lib\site-packages\installed (
    if exist requirements.txt (
        echo Installing dependencies...
        pip install -r requirements.txt
		python.exe -m pip install --upgrade pip
		pip install pyinstaller

        echo. > .venv\Lib\site-packages\installed
    ) else (
        echo requirements.txt not found, skipping dependency installation.
    )
) else (
    echo Dependencies already installed, skipping installation.
)

pyinstaller --onefile --windowed --clean --strip main.py

echo done


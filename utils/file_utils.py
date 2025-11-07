# utils/file_utils.py
from __future__ import annotations
import tempfile
from pathlib import Path

def create_output_directory(input_file_path: str) -> str:
    """Создание выходной директории"""
    try:
        base_name = Path(input_file_path).stem
        output_dir = Path(f"{base_name}_out")
        output_dir.mkdir(parents=True, exist_ok=True)
        return str(output_dir)
    except Exception as e:
        raise Exception(f"Не удалось создать выходную папку: {e}")

def get_temp_dir() -> Path:
    """Получение временной директории"""
    return Path(tempfile.gettempdir())
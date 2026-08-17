# config.py
from __future__ import annotations
import os
from pathlib import Path

# Пути и настройки
ENV_FILE = ".env"
DEFAULT_COORDINATES = {
    "X_START": 14,
    "Y_START": 280,
    "X_END": 77,
    "Y_END": 330,
    "REGEX_PATTERN": r"^[A-Z]{3}U\d{7}$",
}

# OCR настройки
TESSERACT_PATHS = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    Path.home() / "Tesseract-OCR/tesseract.exe",
    Path.home() / "AppData/Local/Tesseract-OCR/tesseract.exe",
    Path.home() / "AppData/Local/Programs/Tesseract-OCR/tesseract.exe",
]

# UI настройки
WINDOW_SIZE = (1400, 800)
CANVAS_SIZE = (750 // 2, 500)
DOUBLE_CLICK_DELAY = 300

# Номера колонок таблицы
NUMBER_COL = 1
EXPECTED_COL = 2
INVOICE_COL = 3
RECOGNIZED_COL = 4
MATCH_COL = 5
SCORE_COL = 6

IDX_NUMBER = NUMBER_COL - 1
IDX_EXPECTED = EXPECTED_COL - 1
IDX_INVOICE = INVOICE_COL - 1
IDX_RECOGNIZED = RECOGNIZED_COL - 1
IDX_MATCH = MATCH_COL - 1
IDX_SCORE = SCORE_COL - 1

# utils/helpers.py
from __future__ import annotations
import tkinter.messagebox as messagebox
from pdf_ocr_app.utils.logger import logger

def safe_execute(func):
    """Декоратор для оборачивания функций с обработкой ошибок и логированием."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка в функции {func.__name__}: {e}", exc_info=True)
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
    return wrapper

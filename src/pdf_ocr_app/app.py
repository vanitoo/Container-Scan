# app.py
from __future__ import annotations

import os

from dotenv import load_dotenv, set_key

from pdf_ocr_app.config import DEFAULT_COORDINATES, ENV_FILE
from pdf_ocr_app.gui.main_window import MainWindow
from pdf_ocr_app.models.state import AppState
from pdf_ocr_app.services.excel_service import ExcelService
from pdf_ocr_app.services.matching_service import MatchingService
from pdf_ocr_app.services.ocr_service import OCRService
from pdf_ocr_app.services.pdf_service import PDFService
from pdf_ocr_app.utils.logger import logger
from pdf_ocr_app.version import __version__


class PDFOCRApp:
    def __init__(self):
        self.version = __version__
        self.state = AppState()
        self._load_environment()

        # Инициализация сервисов
        self.pdf_service = PDFService(self.state)
        self.ocr_service = OCRService(self.state)
        self.excel_service = ExcelService(self.state)
        self.matching_service = MatchingService(self.state, self.ocr_service)

        # Установка взаимных ссылок
        self.state.pdf_service = self.pdf_service
        self.state.ocr_service = self.ocr_service

        # GUI
        self.gui = MainWindow(self)
        self.root = None

    def _load_environment(self):
        """Загрузка настроек из .env файла"""
        load_dotenv(ENV_FILE)
        try:
            self.state.x_start = int(os.getenv("X_START", DEFAULT_COORDINATES["X_START"]))
            self.state.y_start = int(os.getenv("Y_START", DEFAULT_COORDINATES["Y_START"]))
            self.state.x_end = int(os.getenv("X_END", DEFAULT_COORDINATES["X_END"]))
            self.state.y_end = int(os.getenv("Y_END", DEFAULT_COORDINATES["Y_END"]))
            self.state.regex_pattern = os.getenv("REGEX_PATTERN", DEFAULT_COORDINATES["REGEX_PATTERN"])

            # Инициализация selected_areas
            self.state.selected_areas = [
                (None, self.state.x_start, self.state.y_start, self.state.x_end, self.state.y_end)]

            logger.info(f"Загружены координаты из .env: x={self.state.x_start}, y={self.state.y_start}")

        except Exception as e:
            logger.error(f"Ошибка при загрузке координат из .env: {e}")
            self.state.x_start = DEFAULT_COORDINATES["X_START"]
            self.state.y_start = DEFAULT_COORDINATES["Y_START"]
            self.state.x_end = DEFAULT_COORDINATES["X_END"]
            self.state.y_end = DEFAULT_COORDINATES["Y_END"]
            self.state.selected_areas = [
                (None, self.state.x_start, self.state.y_start, self.state.x_end, self.state.y_end)]

    def _save_environment(self):
        """Сохранение настроек в .env файл"""
        try:
            set_key(ENV_FILE, "X_START", str(self.state.x_start))
            set_key(ENV_FILE, "Y_START", str(self.state.y_start))
            set_key(ENV_FILE, "X_END", str(self.state.x_end))
            set_key(ENV_FILE, "Y_END", str(self.state.y_end))
            set_key(ENV_FILE, "REGEX_PATTERN", str(self.state.regex_pattern))
        except Exception as e:
            logger.error(f"Ошибка при сохранении в .env: {e}")

    def run(self):
        """Запуск приложения"""
        try:
            # Настройка логирования
            logger.setup(
                log_file="main_app.log",
                gui_widget=None,  # Будет установлен в GUI
                max_log_size=10 * 1024 * 1024,
                backup_count=5,
                log_level="DEBUG" if self.state.debug_mode else "INFO"
            )

            self.gui.create_interface()
            self.root = self.gui.root

            logger.info("Запуск приложения...")
            logger.info(f"Версия приложения: {self.version}")
            self.ocr_service.check_tesseract()

            # Проверка обновлений
            self._check_for_updates()

            self.gui.run()

        except Exception as e:
            logger.critical(f"Критическая ошибка при запуске: {e}")
            # Показываем ошибку в messagebox если GUI не запустился
            try:
                import tkinter.messagebox as messagebox
                messagebox.showerror("Ошибка запуска", f"Не удалось запустить приложение:\n{e}")
            except Exception:
                print(f"Критическая ошибка: {e}")
            raise

    def _check_for_updates(self):
        """Проверка обновлений"""
        # Можно добавить логику проверки обновлений
        pass

    def on_closing(self):
        """Обработчик закрытия приложения"""
        self._save_environment()
        if self.root:
            self.root.destroy()


def main():
    """Основная функция для запуска приложения."""
    app = PDFOCRApp()
    app.run()


if __name__ == "__main__":
    main()

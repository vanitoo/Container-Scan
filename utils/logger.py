# utils/logger.py
from __future__ import annotations
import logging
import tkinter as tk
from logging import LogRecord
from logging.handlers import RotatingFileHandler
import colorama
from colorama import Fore, Style

colorama.init()

class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.WHITE,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, Fore.WHITE)
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"

class GUILogHandler(logging.Handler):
    def __init__(self, widget: tk.Text):
        super().__init__()
        self.widget = widget
        self.setFormatter(logging.Formatter("%(message)s"))
        self._setup_tags()

    def _setup_tags(self):
        self.widget.tag_config("DEBUG", foreground="cyan")
        self.widget.tag_config("INFO", foreground="black")
        self.widget.tag_config("WARNING", foreground="orange")
        self.widget.tag_config("ERROR", foreground="red")
        self.widget.tag_config("CRITICAL", foreground="red", font=("TkDefaultFont", 12, "bold"))

    def emit(self, record: LogRecord):
        msg = self.format(record)
        self.widget.configure(state="normal")
        self.widget.insert(tk.END, msg + "\n", record.levelname)
        self.widget.see(tk.END)
        self.widget.configure(state="disabled")

class UniversalLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger("CustomLogger")
            self.logger.setLevel(logging.DEBUG)
            self._initialized = True

    def setup(
        self,
        log_file: str | None = "app.log",
        gui_widget: tk.Text | None = None,
        max_log_size: int = 5 * 1024 * 1024,
        backup_count: int = 3,
        log_level: str = "INFO",
    ):
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(level)

        formatter = logging.Formatter("[%(asctime)s] - %(levelname)s - %(message)s")

        if log_file:
            file_handler = RotatingFileHandler(
                log_file, maxBytes=max_log_size, backupCount=backup_count, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColoredFormatter("%(message)s"))
        self.logger.addHandler(console_handler)

        if gui_widget:
            gui_handler = GUILogHandler(gui_widget)
            gui_handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(gui_handler)

    def update_gui_handler(self, widget: tk.Text) -> None:
        for handler in self.logger.handlers[:]:
            if isinstance(handler, GUILogHandler):
                self.logger.removeHandler(handler)

        if widget:
            gui_handler = GUILogHandler(widget)
            gui_handler.setFormatter(logging.Formatter("%(message)s"))
            gui_handler.setLevel(self.logger.level)
            self.logger.addHandler(gui_handler)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)

logger = UniversalLogger()
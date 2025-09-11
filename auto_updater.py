from __future__ import annotations

import logging
import sys
import threading
import tkinter as tk
import tkinter.messagebox as messagebox
from pathlib import Path  # ← добавьте вверху файла

import requests

from version import __version__ as CURRENT_VERSION

logger = logging.getLogger("CustomLogger")


class AutoUpdater:
    UPDATE_URL = "https://api.github.com/repos/vanitoo/pythonProject-OpenCV-PDF/releases/latest"
    DOWNLOAD_URL = "https://github.com/vanitoo/pythonProject-OpenCV-PDF/releases/download/v{version}/main.exe"

    def __init__(self, root):
        self.root = root
        self.add_about_button()
        self.show_version_in_title()
        # Задержка запуска обновления на 10 секунд
        self.root.after(10_000, self.check_for_update_async)

    def get_latest_version(self) -> str:
        logger.info("Проверка обновлений...")
        try:
            logger.info(f"Запрос к {self.UPDATE_URL} для получения информации о последнем релизе...")
            response = requests.get(self.UPDATE_URL, timeout=10)
            response.raise_for_status()
            latest = response.json()["tag_name"].lstrip("v")
            logger.info(f"Получена последняя версия: {latest}")
            return latest
        except Exception as e:
            logger.warning(f"Не удалось получить последнюю версию: {e}")
            return ""

    def is_newer_version(self, latest: str) -> bool:
        return self.compare_versions(CURRENT_VERSION, latest) < 0

    @staticmethod
    def compare_versions(v1, v2):
        def normalize(v):
            return [int(x) for x in v.split(".")]

        return (normalize(v1) > normalize(v2)) - (normalize(v1) < normalize(v2))

    def check_for_update_async(self):
        # Запускаем сетевой запрос в фоне
        threading.Thread(target=self._check_for_update_worker, daemon=True).start()

    def _check_for_update_worker(self):
        latest_version = self.get_latest_version()
        if latest_version and self.is_newer_version(latest_version):
            logger.info(f"Доступна новая версия {latest_version}")
            self.root.after(0, lambda: self._show_notification_window(latest_version))

    def _show_notification_window2(self, latest_version):
        # Простое всплывающее окно в правом нижнем углу
        popup = tk.Toplevel(self.root)
        popup.title("Доступно обновление")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        # UI
        label = tk.Label(popup, text=f"Доступна новая версия: {latest_version}", padx=10, pady=10)
        label.pack()

        btn_frame = tk.Frame(popup)
        btn_frame.pack(pady=(0, 10))

        tk.Button(
            btn_frame, text="Обновить", command=lambda: [popup.destroy(), self.download_update(latest_version)]
        ).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Позже", command=popup.destroy).pack(side="left", padx=5)

        # Позиционирование в правом нижнем углу экрана
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        window_width = popup.winfo_width()
        window_height = popup.winfo_height()
        x = screen_width - window_width - 20
        y = screen_height - window_height - 50
        popup.geometry(f"+{x}+{y}")

    def _show_notification_window(self, latest_version):
        # Создаём окно *скрытым*, чтобы не мигало
        popup = tk.Toplevel(self.root)
        popup.withdraw()  # ← скрываем сразу
        popup.title("Доступно обновление")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.transient(self.root)  # не светиться в панели задач (аккуратнее в macOS/Linux)

        # UI
        label = tk.Label(popup, text=f"Доступна новая версия: {latest_version}", padx=10, pady=10)
        label.pack()

        btn_frame = tk.Frame(popup)
        btn_frame.pack(pady=(0, 10))
        tk.Button(
            btn_frame, text="Обновить", command=lambda: [popup.destroy(), self.download_update(latest_version)]
        ).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Позже", command=popup.destroy).pack(side="left", padx=5)

        # Сначала полностью посчитать размеры...
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        window_width = popup.winfo_width()
        window_height = popup.winfo_height()
        x = screen_width - window_width - 20
        y = screen_height - window_height - 50
        popup.geometry(f"+{x}+{y}")

        # ...и только теперь показать
        popup.deiconify()

    def download_update(self, version: str):
        url = self.DOWNLOAD_URL.format(version=version)
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            exe_path = Path(sys.executable).parent / f"main_{version}.exe"
            logger.info(f"Загрузка обновления с {url}")
            with exe_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.info("Обновление успешно загружено.")
            messagebox.showinfo("Обновление завершено", "Файл обновлён. Пожалуйста, перезапустите программу.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке обновления: {e}")
            messagebox.showerror("Ошибка обновления", f"Не удалось загрузить обновление:\n{e}")

    def add_about_button(self):
        from tkinter import ttk

        about_button = ttk.Button(self.root, text="О программе", command=self.show_about)
        about_button.pack(anchor="ne", padx=10, pady=10)

    def show_about(self):
        messagebox.showinfo(
            "О программе",
            f"Текущая версия: {CURRENT_VERSION}\nПроект с открытым исходным кодом.\nGitHub: https://github.com/vanitoo/pythonProject-OpenCV-PDF",
        )

    def show_version_in_title(self):
        self.root.title(f"OpenCV PDF - Версия: {CURRENT_VERSION}")

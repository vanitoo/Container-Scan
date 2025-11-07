# utils/updater.py
from __future__ import annotations
import logging
import sys
import threading
import tkinter as tk
import tkinter.messagebox as messagebox
from pathlib import Path
from tkinter import ttk
import requests

from version import __version__ as CURRENT_VERSION
from utils.logger import logger

class AutoUpdater:
    UPDATE_URL = "https://api.github.com/repos/vanitoo/pythonProject-OpenCV-PDF/releases/latest"
    DOWNLOAD_URL = "https://github.com/vanitoo/pythonProject-OpenCV-PDF/releases/download/v{version}/main.exe"

    def __init__(self, root):
        self.root = root
        self.download_cancelled = False
        self.add_about_button()
        self.show_version_in_title()
        if getattr(sys, 'frozen', False):
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
        threading.Thread(target=self._check_for_update_worker, daemon=True).start()

    def _check_for_update_worker(self):
        latest_version = self.get_latest_version()
        if latest_version and self.is_newer_version(latest_version):
            logger.info(f"Доступна новая версия {latest_version}")
            self.root.after(0, lambda: self._show_notification_window(latest_version))

    def _show_notification_window(self, latest_version):
        popup = tk.Toplevel(self.root)
        popup.title("Доступно обновление")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.transient(self.root)

        tk.Label(popup, text=f"Доступна новая версия: {latest_version}", padx=10, pady=10).pack()
        tk.Label(popup, text="Текущая версия будет заменена автоматически.", padx=10).pack()

        btn_frame = tk.Frame(popup)
        btn_frame.pack(pady=(0, 10))

        ttk.Button(
            btn_frame,
            text="Обновить сейчас",
            command=lambda: [popup.destroy(), self.download_update(latest_version)]
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_frame,
            text="Напомнить позже",
            command=popup.destroy
        ).pack(side="left", padx=5)

        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        window_width = popup.winfo_width()
        window_height = popup.winfo_height()
        x = screen_width - window_width - 20
        y = screen_height - window_height - 50
        popup.geometry(f"+{x}+{y}")

    def download_update(self, version: str):
        url = self.DOWNLOAD_URL.format(version=version)
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Загрузка обновления")
        progress_window.geometry("400x150")
        progress_window.resizable(False, False)
        progress_window.transient(self.root)
        progress_window.grab_set()

        progress_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - progress_window.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - progress_window.winfo_height()) // 2
        progress_window.geometry(f"+{x}+{y}")

        tk.Label(progress_window, text=f"Загрузка версии {version}", font=("Arial", 12)).pack(pady=10)
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, length=350)
        progress_bar.pack(pady=10)
        status_label = tk.Label(progress_window, text="Подготовка...")
        status_label.pack(pady=5)
        cancel_button = ttk.Button(progress_window, text="Отмена", command=lambda: self._cancel_download(progress_window))
        cancel_button.pack(pady=5)

        self.download_cancelled = False
        threading.Thread(
            target=self._download_worker,
            args=(url, version, progress_var, status_label, progress_window),
            daemon=True
        ).start()

    def _download_worker(self, url: str, version: str, progress_var, status_label, progress_window):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            exe_path = Path(sys.executable).parent / f"main_{version}.exe"

            self.root.after(0, lambda: status_label.config(text="Загрузка начата..."))
            with exe_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.download_cancelled:
                        self.root.after(0, progress_window.destroy)
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            self.root.after(0, lambda p=progress: progress_var.set(p))
                            downloaded_mb = downloaded_size / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            status_text = f"Загружено: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({progress:.1f}%)"
                            self.root.after(0, lambda t=status_text: status_label.config(text=t))
            self.root.after(0, lambda: self._download_completed(version, progress_window))
        except Exception as e:
            self.root.after(0, lambda: self._download_failed(e, progress_window))

    def _download_completed(self, version: str, progress_window):
        progress_window.destroy()
        logger.info(f"Обновление версии {version} успешно загружено")
        result = messagebox.askyesno(
            "Обновление загружено",
            f"Версия {version} успешно загружена!\n\n"
            "Хотите перезапустить приложение для применения обновления?\n\n"
            "Если выберете 'Нет', обновление будет применено при следующем запуске."
        )
        if result:
            self._restart_application(version)
        else:
            messagebox.showinfo("Обновление", "Обновление будет применено при следующем запуске приложения.")

    def _download_failed(self, error: Exception, progress_window):
        progress_window.destroy()
        error_msg = f"Ошибка при загрузке обновления: {error}"
        logger.error(error_msg)
        messagebox.showerror("Ошибка обновления", error_msg)

    def _cancel_download(self, progress_window):
        self.download_cancelled = True
        progress_window.destroy()
        messagebox.showinfo("Отменено", "Загрузка обновления отменена.")

    def _restart_application(self, version: str):
        try:
            messagebox.showinfo(
                "Обновление загружено",
                f"Версия {version} успешно загружена!\n\n"
                "Пожалуйста, закройте приложение и запустите его снова\n"
                "для применения обновления.\n\n"
                f"Файл обновления: main_{version}.exe"
            )
            self.root.quit()
        except Exception as e:
            print(f"Ошибка при перезапуске: {e}")
            messagebox.showerror("Ошибка", f"Не удалось перезапустить приложение: {e}")

    def add_about_button(self):
        about_button = ttk.Button(self.root, text="О программе", command=self.show_about)
        about_button.pack(anchor="ne", padx=10, pady=10)

    def show_about(self):
        messagebox.showinfo(
            "О программе",
            f"Текущая версия: {CURRENT_VERSION}\nПроект с открытым исходным кодом.\nGitHub: https://github.com/vanitoo/pythonProject-OpenCV-PDF",
        )

    def show_version_in_title(self):
        self.root.title(f"OpenCV PDF - Версия: {CURRENT_VERSION}")
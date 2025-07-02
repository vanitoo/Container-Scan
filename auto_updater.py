from __future__ import annotations

import os
import shutil
import sys
import tkinter as tk
import webbrowser
from tkinter import messagebox

import requests


class AutoUpdater:
    UPDATE_URL = "https://github.com/vanitoo/pythonProject-OpenCV-PDF/releases/latest"
    DOWNLOAD_URL = "https://github.com/vanitoo/pythonProject-OpenCV-PDF/releases/download/v{version}/main.exe"
    from version import __version__

    CURRENT_VERSION = __version__
    LOCAL_EXE = "main.exe"
    NEW_EXE = "main_new.exe"

    def __init__(self, parent):
        self.add_about_button(parent)
        self.show_version_in_title(parent)
        self.parent = parent

    def check_for_update(self):
        latest_version = self.get_latest_version()
        if not latest_version:
            return

        if self.is_newer_version(latest_version):
            result = messagebox.askyesno("Обновление доступно", f"Доступна новая версия {latest_version}. Обновить?")
            if result:
                self.download_update(latest_version)

    def get_latest_version(self):
        try:
            response = requests.get(
                "https://raw.githubusercontent.com/vanitoo/pythonProject-OpenCV-PDF/main/VERSION", timeout=5
            )
            if response.status_code == 200:
                return response.text.strip()
        except Exception as e:
            print(f"Ошибка получения версии: {e}")
        return None

    def is_newer_version(self, latest):
        return latest > self.CURRENT_VERSION

    def download_update(self, version):
        try:
            url = self.DOWNLOAD_URL.format(version=version)
            dest_path = os.path.join(os.path.dirname(sys.executable), self.NEW_EXE)

            with requests.get(url, stream=True, timeout=10) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    shutil.copyfileobj(r.raw, f)

            messagebox.showinfo("Обновление", f"Обновление загружено как {self.NEW_EXE}. Перезапустить приложение?")
            self.prompt_restart()

        except Exception as e:
            messagebox.showerror("Ошибка обновления", f"Не удалось скачать обновление: {e}")

    def show_version_in_title(self, root):
        latest = self.get_latest_version()
        if latest and self.is_newer_version(latest):
            root.title(f"OpenCV PDF - Версия: {self.CURRENT_VERSION} (Доступна: {latest})")
        else:
            root.title(f"OpenCV PDF - Версия: {self.CURRENT_VERSION}")

    def add_about_button(self, root):
        about_button = tk.Button(root, text="О программе", command=self.show_about_info)
        about_button.pack(side=tk.TOP, anchor="ne", padx=10, pady=5)

    def show_about_info(self):
        top = tk.Toplevel(self.parent)
        top.title("О программе")
        top.geometry("400x150")

        label = tk.Label(top, text=f"Текущая версия: {self.CURRENT_VERSION}", font=("Arial", 12))
        label.pack(pady=10)

        link = tk.Label(top, text="Открыть GitHub релиз", fg="blue", cursor="hand2")
        link.pack()
        link.bind(
            "<Button-1>",
            lambda e: webbrowser.open_new_tab("https://github.com/vanitoo/pythonProject-OpenCV-PDF/releases"),
        )

        result = messagebox.askyesno("Перезапуск", "Перезапустить приложение сейчас?")
        if result:
            os.execv(sys.executable, [sys.executable] + sys.argv)

    @staticmethod
    def check_post_restart():
        old_path = os.path.join(os.path.dirname(sys.executable), AutoUpdater.LOCAL_EXE)
        new_path = os.path.join(os.path.dirname(sys.executable), AutoUpdater.NEW_EXE)

        if os.path.exists(new_path):
            result = messagebox.askyesno(
                "Обновление завершено", f"Найден {AutoUpdater.NEW_EXE}. Заменить текущий {AutoUpdater.LOCAL_EXE}?"
            )
            if result:
                try:
                    os.remove(old_path)
                    os.rename(new_path, old_path)
                    messagebox.showinfo("Успешно", "Обновление завершено. Запустите программу снова.")
                    sys.exit(0)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось заменить файл: {e}")

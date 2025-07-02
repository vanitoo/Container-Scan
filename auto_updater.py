from __future__ import annotations

import os
import shutil
import sys
import tkinter as tk
import webbrowser
from tkinter import messagebox
import requests
import logging
import threading
import time

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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
        self.schedule_auto_update()


    def schedule_auto_update(self, interval_minutes=1):
        """Запланировать автообновление через каждые 30 минут"""
        logger.info(f"Автообновление будет проверяться каждые {interval_minutes} минут.")
        threading.Timer(interval_minutes * 60, self.check_for_update).start()

    def check_for_update(self):
        logger.info("Проверка наличия обновлений...")
        latest_version = self.get_latest_version()
        if not latest_version:
            logger.error("Не удалось получить информацию о последней версии.")
            return

        if self.is_newer_version(latest_version):
            logger.info(f"Доступна новая версия {latest_version}. Пользователю предложено обновить.")
            result = messagebox.askyesno("Обновление доступно", f"Доступна новая версия {latest_version}. Обновить?")
            if result:
                logger.info("Пользователь согласился на обновление.")
                self.download_update(latest_version)
            else:
                logger.info("Пользователь отклонил обновление.")
        else:
            logger.info("У вас установлена последняя версия.")

        self.schedule_auto_update()

    def get_latest_version(self):
        try:
            # URL для получения информации о релизах
            repo_url = "https://api.github.com/repos/vanitoo/pythonProject-OpenCV-PDF/releases/latest"
            logger.info(f"Запрос к {repo_url} для получения информации о последнем релизе...")

            # Отправляем запрос к GitHub API
            response = requests.get(repo_url, timeout=5)

            # Если запрос успешен
            if response.status_code == 200:
                latest_release = response.json()
                latest_version = latest_release["tag_name"].lstrip("v")  # Убираем префикс 'v'

                logger.info(f"Получена последняя версия: {latest_version}")
                return latest_version
            else:
                logger.error(f"Ошибка при запросе: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Ошибка получения последней версии: {e}")
            return None

    def is_newer_version(self, latest):
        return latest > self.CURRENT_VERSION

    def download_update(self, version):
        try:
            logger.info(f"Запуск скачивания обновления для версии {version}...")
            url = self.DOWNLOAD_URL.format(version=version)
            dest_path = os.path.join(os.path.dirname(sys.executable), self.NEW_EXE)

            logger.info(f"Скачивание обновления с URL: {url}")
            with requests.get(url, stream=True, timeout=10) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    shutil.copyfileobj(r.raw, f)

            logger.info(f"Обновление загружено как {self.NEW_EXE}")
            messagebox.showinfo("Обновление", f"Обновление загружено как {self.NEW_EXE}. Перезапустить приложение?")
            self.prompt_restart()  # Перезапускаем приложение с новым файлом

        except Exception as e:
            logger.error(f"Не удалось скачать обновление: {e}")
            messagebox.showerror("Ошибка обновления", f"Не удалось скачать обновление: {e}")

    def prompt_restart(self):
        result = messagebox.askyesno("Перезапуск", "Обновление загружено. Перезапустить приложение?")
        if result:
            self.replace_old_with_new()
            messagebox.showinfo("Успех", "Обновление завершено. Программа будет перезапущена.")
            sys.exit(0)
        else:
            logger.info("Обновление не будет установлено.")

    def replace_old_with_new(self):
        old_path = os.path.join(os.path.dirname(sys.executable), self.LOCAL_EXE)
        new_path = os.path.join(os.path.dirname(sys.executable), self.NEW_EXE)

        try:
            os.remove(old_path)
            os.rename(new_path, old_path)
        except Exception as e:
            logger.error(f"Не удалось заменить файл: {e}")
            messagebox.showerror("Ошибка", f"Не удалось заменить файл: {e}")

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

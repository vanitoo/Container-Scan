# utils/updater.py
from __future__ import annotations
import hashlib
import hmac
import os
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.messagebox as messagebox
from pathlib import Path
from tkinter import ttk
import requests

from pdf_ocr_app.utils.logger import logger
from pdf_ocr_app.version import __version__ as CURRENT_VERSION

class AutoUpdater:
    UPDATE_URL = "https://api.github.com/repos/vanitoo/container-scan/releases/latest"
    DOWNLOAD_URL_PREFIX = "https://github.com/vanitoo/container-scan/releases/download/"

    def __init__(self, root, add_about_button: bool = True):
        self.root = root
        self.download_cancelled = False
        self.latest_asset = None
        if add_about_button:
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
            release = response.json()
            latest = release["tag_name"].lstrip("v")
            self.latest_asset = next(
                (asset for asset in release.get("assets", []) if asset.get("name") == "ContainerScan.exe"),
                None,
            )
            if self.latest_asset is None:
                raise ValueError("Релиз не содержит файл ContainerScan.exe")

            digest = self.latest_asset.get("digest", "")
            digest_value = digest.removeprefix("sha256:")
            if (
                not digest.startswith("sha256:")
                or len(digest_value) != 64
                or any(char not in "0123456789abcdefABCDEF" for char in digest_value)
            ):
                raise ValueError("GitHub Release не содержит корректный SHA-256 для ContainerScan.exe")

            download_url = self.latest_asset.get("browser_download_url", "")
            # GitHub отдаёт в browser_download_url канонический регистр имени
            # репозитория (например, "Container-Scan"), а префикс записан строчными
            # буквами, поэтому сравниваем без учёта регистра.
            if not download_url.lower().startswith(self.DOWNLOAD_URL_PREFIX.lower()):
                raise ValueError("GitHub Release содержит недоверенный адрес файла обновления")
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
        if not self.latest_asset:
            messagebox.showerror("Ошибка обновления", "Нет проверенных метаданных файла обновления.")
            return

        url = self.latest_asset["browser_download_url"]
        expected_digest = self.latest_asset["digest"].removeprefix("sha256:").lower()
        expected_size = int(self.latest_asset.get("size", 0))
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
            args=(url, version, expected_digest, expected_size, progress_var, status_label, progress_window),
            daemon=True
        ).start()

    def _download_worker(
        self, url: str, version: str, expected_digest: str, expected_size: int,
        progress_var, status_label, progress_window,
    ):
        exe_path = Path(sys.executable).parent / f"ContainerScan_{version}.exe"
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            hasher = hashlib.sha256()

            self.root.after(0, lambda: status_label.config(text="Загрузка начата..."))
            with exe_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.download_cancelled:
                        exe_path.unlink(missing_ok=True)
                        self.root.after(0, progress_window.destroy)
                        return
                    if chunk:
                        f.write(chunk)
                        hasher.update(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            self.root.after(0, lambda p=progress: progress_var.set(p))
                            downloaded_mb = downloaded_size / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            status_text = f"Загружено: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({progress:.1f}%)"
                            self.root.after(0, lambda t=status_text: status_label.config(text=t))
            if expected_size > 0 and downloaded_size != expected_size:
                raise ValueError(
                    f"Размер обновления не совпадает: ожидалось {expected_size}, получено {downloaded_size} байт"
                )

            actual_digest = hasher.hexdigest()
            if not hmac.compare_digest(actual_digest, expected_digest):
                raise ValueError("SHA-256 обновления не совпадает с хешем GitHub Release")

            logger.info(f"SHA-256 обновления проверен: {actual_digest}")
            self.root.after(0, lambda: self._download_completed(version, progress_window))
        except Exception as e:
            exe_path.unlink(missing_ok=True)
            self.root.after(0, lambda error=e: self._download_failed(error, progress_window))

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
            current_exe = Path(sys.executable).resolve()
            update_exe = current_exe.parent / f"ContainerScan_{version}.exe"
            if not update_exe.is_file():
                raise FileNotFoundError(f"Файл обновления не найден: {update_exe}")

            helper_script = current_exe.parent / ".container_scan_update.ps1"
            helper_log = current_exe.parent / "update_error.log"
            script = r'''param(
    [Parameter(Mandatory=$true)][int]$ParentProcessId,
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Target,
    [Parameter(Mandatory=$true)][string]$WorkingDirectory,
    [Parameter(Mandatory=$true)][string]$LogPath
)
$ErrorActionPreference = "Stop"
try {
    Wait-Process -Id $ParentProcessId -Timeout 60 -ErrorAction SilentlyContinue
    $replaced = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            Move-Item -LiteralPath $Source -Destination $Target -Force
            $replaced = $true
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $replaced) { throw "Could not replace the running executable after 30 attempts." }
    Start-Process -FilePath $Target -WorkingDirectory $WorkingDirectory
    Remove-Item -LiteralPath $LogPath -Force -ErrorAction SilentlyContinue
} catch {
    "$(Get-Date -Format o) $($_.Exception.Message)" | Set-Content -LiteralPath $LogPath -Encoding UTF8
    exit 1
} finally {
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
'''
            helper_script.write_text(script, encoding="utf-8")

            creation_flags = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            )
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-WindowStyle", "Hidden",
                    "-File", str(helper_script),
                    "-ParentProcessId", str(os.getpid()),
                    "-Source", str(update_exe),
                    "-Target", str(current_exe),
                    "-WorkingDirectory", str(current_exe.parent),
                    "-LogPath", str(helper_log),
                ],
                cwd=str(current_exe.parent),
                creationflags=creation_flags,
                close_fds=True,
            )
            logger.info(
                f"Запущена установка обновления {version}: {update_exe.name} -> {current_exe.name}"
            )
            self.root.destroy()
        except Exception as e:
            logger.error(f"Ошибка при запуске установки обновления: {e}", exc_info=True)
            messagebox.showerror("Ошибка", f"Не удалось перезапустить приложение: {e}")

    def add_about_button(self):
        about_button = ttk.Button(self.root, text="О программе", command=self.show_about)
        about_button.pack(anchor="ne", padx=10, pady=10)

    def show_about(self):
        messagebox.showinfo(
            "О программе",
            f"ContainerScan\nТекущая версия: {CURRENT_VERSION}\nПроект с открытым исходным кодом.\nGitHub: https://github.com/vanitoo/container-scan",
        )

    def show_version_in_title(self):
        self.root.title(f"ContainerScan — версия {CURRENT_VERSION}")

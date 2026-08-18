from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.messagebox as messagebox
import webbrowser
from pathlib import Path
from tkinter import ttk

import requests

from pdf_ocr_app.utils.logger import logger
from pdf_ocr_app.version import __version__ as CURRENT_VERSION


class AutoUpdater:
    UPDATE_URL = "https://api.github.com/repos/vanitoo/container-scan/releases/latest"
    DOWNLOAD_URL_PREFIX = "https://github.com/vanitoo/container-scan/releases/download/"
    REPOSITORY_URL = "https://github.com/vanitoo/Container-Scan"
    PENDING_MANIFEST = ".container_scan_pending_update.json"

    def __init__(self, root, add_about_button: bool = True):
        self.root = root
        self.download_cancelled = False
        self.latest_asset = None

        if add_about_button:
            self.add_about_button()
        self.show_version_in_title()

        # Автообновление имеет смысл только для собранного PyInstaller EXE.
        if getattr(sys, "frozen", False):
            # Сначала применяем ранее скачанное отложенное обновление.
            self.root.after(1_000, self._apply_pending_update_on_startup)
            # Если отложенного обновления нет — обычная фоновая проверка GitHub.
            self.root.after(10_000, self.check_for_update_async)

    @property
    def application_dir(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path.cwd()

    @property
    def pending_manifest_path(self) -> Path:
        return self.application_dir / self.PENDING_MANIFEST

    def get_latest_version(self) -> str:
        logger.info("Проверка обновлений...")
        try:
            logger.info(
                f"Запрос к {self.UPDATE_URL} для получения информации о последнем релизе..."
            )
            response = requests.get(self.UPDATE_URL, timeout=10)
            response.raise_for_status()
            release = response.json()
            latest = release["tag_name"].lstrip("v")

            self.latest_asset = next(
                (
                    asset
                    for asset in release.get("assets", [])
                    if asset.get("name") == "ContainerScan.exe"
                ),
                None,
            )
            if self.latest_asset is None:
                raise ValueError("Релиз не содержит файл ContainerScan.exe")

            digest = self.latest_asset.get("digest", "")
            digest_value = digest.removeprefix("sha256:")
            if (
                not digest.startswith("sha256:")
                or len(digest_value) != 64
                or any(
                    char not in "0123456789abcdefABCDEF"
                    for char in digest_value
                )
            ):
                raise ValueError(
                    "GitHub Release не содержит корректный SHA-256 для ContainerScan.exe"
                )

            download_url = self.latest_asset.get("browser_download_url", "")
            if not download_url.lower().startswith(
                self.DOWNLOAD_URL_PREFIX.lower()
            ):
                raise ValueError(
                    "GitHub Release содержит недоверенный адрес файла обновления"
                )

            logger.info(f"Получена последняя версия: {latest}")
            return latest
        except Exception as exc:
            logger.warning(f"Не удалось получить последнюю версию: {exc}")
            return ""

    def is_newer_version(self, latest: str) -> bool:
        return self.compare_versions(CURRENT_VERSION, latest) < 0

    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        def normalize(version: str) -> list[int]:
            return [int(part) for part in version.split(".")]

        first = normalize(v1)
        second = normalize(v2)
        return (first > second) - (first < second)

    # ------------------------------------------------------------------
    # Проверка обновлений
    # ------------------------------------------------------------------

    def check_for_update_async(self):
        threading.Thread(
            target=self._check_for_update_worker,
            daemon=True,
        ).start()

    def _check_for_update_worker(self):
        latest_version = self.get_latest_version()
        if latest_version and self.is_newer_version(latest_version):
            logger.info(f"Доступна новая версия {latest_version}")
            self.root.after(
                0,
                lambda: self._show_notification_window(latest_version),
            )

    def check_for_update_manual(self):
        """Ручная проверка из окна «О программе»."""
        logger.info("Запущена ручная проверка обновлений")
        threading.Thread(
            target=self._manual_check_worker,
            daemon=True,
        ).start()

    def _manual_check_worker(self):
        latest_version = self.get_latest_version()
        self.root.after(
            0,
            lambda: self._show_manual_check_result(latest_version),
        )

    def _show_manual_check_result(self, latest_version: str):
        if not latest_version:
            messagebox.showerror(
                "Проверка обновлений",
                "Не удалось получить информацию о последнем релизе.\n"
                "Подробности смотрите в логе приложения.",
                parent=self.root,
            )
            return

        if not self.is_newer_version(latest_version):
            messagebox.showinfo(
                "Проверка обновлений",
                f"Установлена актуальная версия {CURRENT_VERSION}.",
                parent=self.root,
            )
            return

        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Доступно обновление",
                f"Доступна версия {latest_version}.\n\n"
                "Автоматическая установка выполняется только из собранного "
                "ContainerScan.exe.",
                parent=self.root,
            )
            return

        self._show_notification_window(latest_version)

    def _show_notification_window(self, latest_version: str):
        popup = tk.Toplevel(self.root)
        popup.title("Доступно обновление")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.transient(self.root)

        tk.Label(
            popup,
            text=f"Доступна новая версия: {latest_version}",
            padx=10,
            pady=10,
        ).pack()
        tk.Label(
            popup,
            text="Текущая версия будет заменена автоматически.",
            padx=10,
        ).pack()

        btn_frame = tk.Frame(popup)
        btn_frame.pack(pady=(0, 10))

        ttk.Button(
            btn_frame,
            text="Обновить сейчас",
            command=lambda: [
                popup.destroy(),
                self.download_update(latest_version),
            ],
        ).pack(side="left", padx=5)

        ttk.Button(
            btn_frame,
            text="Напомнить позже",
            command=popup.destroy,
        ).pack(side="left", padx=5)

        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        window_width = popup.winfo_width()
        window_height = popup.winfo_height()
        x = screen_width - window_width - 20
        y = screen_height - window_height - 50
        popup.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Загрузка
    # ------------------------------------------------------------------

    def download_update(self, version: str):
        if not getattr(sys, "frozen", False):
            messagebox.showwarning(
                "Обновление",
                "Автоматическая установка доступна только в ContainerScan.exe.",
                parent=self.root,
            )
            return

        if not self.latest_asset:
            messagebox.showerror(
                "Ошибка обновления",
                "Нет проверенных метаданных файла обновления.",
            )
            return

        url = self.latest_asset["browser_download_url"]
        expected_digest = self.latest_asset["digest"].removeprefix(
            "sha256:"
        ).lower()
        expected_size = int(self.latest_asset.get("size", 0))

        progress_window = tk.Toplevel(self.root)
        progress_window.title("Загрузка обновления")
        progress_window.geometry("400x150")
        progress_window.resizable(False, False)
        progress_window.transient(self.root)
        progress_window.grab_set()

        progress_window.update_idletasks()
        x = (
            self.root.winfo_x()
            + (self.root.winfo_width() - progress_window.winfo_width()) // 2
        )
        y = (
            self.root.winfo_y()
            + (self.root.winfo_height() - progress_window.winfo_height()) // 2
        )
        progress_window.geometry(f"+{x}+{y}")

        tk.Label(
            progress_window,
            text=f"Загрузка версии {version}",
            font=("Arial", 12),
        ).pack(pady=10)
        progress_var = tk.DoubleVar()
        ttk.Progressbar(
            progress_window,
            variable=progress_var,
            maximum=100,
            length=350,
        ).pack(pady=10)
        status_label = tk.Label(progress_window, text="Подготовка...")
        status_label.pack(pady=5)
        ttk.Button(
            progress_window,
            text="Отмена",
            command=lambda: self._cancel_download(progress_window),
        ).pack(pady=5)

        self.download_cancelled = False
        threading.Thread(
            target=self._download_worker,
            args=(
                url,
                version,
                expected_digest,
                expected_size,
                progress_var,
                status_label,
                progress_window,
            ),
            daemon=True,
        ).start()

    def _download_worker(
        self,
        url: str,
        version: str,
        expected_digest: str,
        expected_size: int,
        progress_var,
        status_label,
        progress_window,
    ):
        exe_path = self.application_dir / f"ContainerScan_{version}.exe"
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0
            hasher = hashlib.sha256()

            self.root.after(
                0,
                lambda: status_label.config(text="Загрузка начата..."),
            )
            with exe_path.open("wb") as file_handle:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.download_cancelled:
                        exe_path.unlink(missing_ok=True)
                        self.root.after(0, progress_window.destroy)
                        return
                    if not chunk:
                        continue

                    file_handle.write(chunk)
                    hasher.update(chunk)
                    downloaded_size += len(chunk)
                    if total_size > 0:
                        progress = downloaded_size / total_size * 100
                        self.root.after(
                            0,
                            lambda value=progress: progress_var.set(value),
                        )
                        downloaded_mb = downloaded_size / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        status_text = (
                            f"Загружено: {downloaded_mb:.1f} MB / "
                            f"{total_mb:.1f} MB ({progress:.1f}%)"
                        )
                        self.root.after(
                            0,
                            lambda text=status_text: status_label.config(
                                text=text
                            ),
                        )

            if expected_size > 0 and downloaded_size != expected_size:
                raise ValueError(
                    "Размер обновления не совпадает: "
                    f"ожидалось {expected_size}, получено "
                    f"{downloaded_size} байт"
                )

            actual_digest = hasher.hexdigest()
            if not hmac.compare_digest(actual_digest, expected_digest):
                raise ValueError(
                    "SHA-256 обновления не совпадает с хешем GitHub Release"
                )

            self._write_pending_manifest(
                version,
                exe_path,
                actual_digest,
            )
            logger.info(f"SHA-256 обновления проверен: {actual_digest}")
            logger.info(
                f"Обновление подготовлено к установке: {exe_path.name}"
            )
            self.root.after(
                0,
                lambda: self._download_completed(version, progress_window),
            )
        except Exception as exc:
            exe_path.unlink(missing_ok=True)
            self._clear_pending_manifest()
            self.root.after(
                0,
                lambda error=exc: self._download_failed(
                    error,
                    progress_window,
                ),
            )

    def _download_completed(self, version: str, progress_window):
        progress_window.destroy()
        logger.info(f"Обновление версии {version} успешно загружено")
        result = messagebox.askyesno(
            "Обновление загружено",
            f"Версия {version} успешно загружена!\n\n"
            "Хотите перезапустить приложение для применения обновления?\n\n"
            "Если выберете «Нет», обновление будет автоматически применено "
            "при следующем запуске ContainerScan.",
        )
        if result:
            self._restart_application(version)
        else:
            messagebox.showinfo(
                "Обновление",
                "Обновление сохранено и будет применено при следующем запуске приложения.",
            )

    def _download_failed(self, error: Exception, progress_window):
        if progress_window.winfo_exists():
            progress_window.destroy()
        error_msg = f"Ошибка при загрузке обновления: {error}"
        logger.error(error_msg)
        messagebox.showerror("Ошибка обновления", error_msg)

    def _cancel_download(self, progress_window):
        self.download_cancelled = True
        if progress_window.winfo_exists():
            progress_window.destroy()
        messagebox.showinfo("Отменено", "Загрузка обновления отменена.")

    # ------------------------------------------------------------------
    # Отложенное обновление
    # ------------------------------------------------------------------

    def _write_pending_manifest(
        self,
        version: str,
        exe_path: Path,
        digest: str,
    ) -> None:
        data = {
            "version": version,
            "file": exe_path.name,
            "sha256": digest.lower(),
        }
        temp_path = self.pending_manifest_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.pending_manifest_path)

    def _clear_pending_manifest(self) -> None:
        self.pending_manifest_path.unlink(missing_ok=True)

    @staticmethod
    def _file_sha256(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _load_valid_pending_update(self) -> tuple[str, Path] | None:
        manifest_path = self.pending_manifest_path
        if not manifest_path.is_file():
            return None

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            version = str(data["version"])
            filename = str(data["file"])
            expected_digest = str(data["sha256"]).lower()

            # Не позволяем manifest указывать файл вне каталога приложения.
            update_path = (self.application_dir / filename).resolve()
            if update_path.parent != self.application_dir.resolve():
                raise ValueError("Некорректный путь файла отложенного обновления")
            if not update_path.is_file():
                raise FileNotFoundError(
                    f"Файл отложенного обновления не найден: {update_path}"
                )
            if not self.is_newer_version(version):
                logger.info(
                    f"Отложенное обновление {version} больше не требуется"
                )
                update_path.unlink(missing_ok=True)
                self._clear_pending_manifest()
                return None

            actual_digest = self._file_sha256(update_path)
            if not hmac.compare_digest(actual_digest, expected_digest):
                raise ValueError(
                    "SHA-256 отложенного обновления не совпадает с сохранённым значением"
                )

            return version, update_path
        except Exception as exc:
            logger.error(
                f"Отложенное обновление повреждено или недействительно: {exc}"
            )
            self._clear_pending_manifest()
            return None

    def _apply_pending_update_on_startup(self):
        pending = self._load_valid_pending_update()
        if pending is None:
            return

        version, _update_path = pending
        logger.info(
            f"Найдено отложенное обновление {version}; запускается установка"
        )
        self._restart_application(version)

    # ------------------------------------------------------------------
    # Установка / перезапуск
    # ------------------------------------------------------------------

    def _restart_application(self, version: str):
        try:
            if not getattr(sys, "frozen", False):
                raise RuntimeError(
                    "Автоматическая замена доступна только для собранного EXE"
                )

            pending = self._load_valid_pending_update()
            if pending is None:
                raise FileNotFoundError(
                    "Подготовленное обновление не найдено или не прошло проверку"
                )

            pending_version, update_exe = pending
            if pending_version != version:
                raise ValueError(
                    f"Ожидалась версия {version}, подготовлена {pending_version}"
                )

            current_exe = Path(sys.executable).resolve()
            helper_script = current_exe.parent / ".container_scan_update.ps1"
            helper_log = current_exe.parent / "update_error.log"

            script = r'''param(
    [Parameter(Mandatory=$true)][int]$ParentProcessId,
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Target,
    [Parameter(Mandatory=$true)][string]$WorkingDirectory,
    [Parameter(Mandatory=$true)][string]$ManifestPath,
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
    if (-not $replaced) {
        throw "Could not replace the running executable after 30 attempts."
    }
    Remove-Item -LiteralPath $ManifestPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $LogPath -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath $Target -WorkingDirectory $WorkingDirectory
} catch {
    "$(Get-Date -Format o) $($_.Exception.Message)" |
        Set-Content -LiteralPath $LogPath -Encoding UTF8
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

            # Важно для PyInstaller one-file: дочерний процесс не должен
            # наследовать runtime-окружение текущего распакованного EXE.
            env = os.environ.copy()
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-WindowStyle",
                    "Hidden",
                    "-File",
                    str(helper_script),
                    "-ParentProcessId",
                    str(os.getpid()),
                    "-Source",
                    str(update_exe),
                    "-Target",
                    str(current_exe),
                    "-WorkingDirectory",
                    str(current_exe.parent),
                    "-ManifestPath",
                    str(self.pending_manifest_path),
                    "-LogPath",
                    str(helper_log),
                ],
                cwd=str(current_exe.parent),
                creationflags=creation_flags,
                close_fds=True,
                env=env,
            )
            logger.info(
                f"Запущена установка обновления {version}: "
                f"{update_exe.name} -> {current_exe.name}"
            )
            self.root.destroy()
        except Exception as exc:
            logger.error(
                f"Ошибка при запуске установки обновления: {exc}",
                exc_info=True,
            )
            messagebox.showerror(
                "Ошибка",
                f"Не удалось перезапустить приложение: {exc}",
            )

    # ------------------------------------------------------------------
    # О программе
    # ------------------------------------------------------------------

    def add_about_button(self):
        ttk.Button(
            self.root,
            text="О программе",
            command=self.show_about,
        ).pack(anchor="ne", padx=10, pady=10)

    def show_about(self):
        existing = getattr(self, "_about_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return

        dialog = tk.Toplevel(self.root)
        self._about_window = dialog
        dialog.title("О программе")
        dialog.resizable(False, False)
        dialog.transient(self.root)

        ttk.Label(
            dialog,
            text="ContainerScan",
            font=("Segoe UI Semibold", 13),
        ).pack(padx=20, pady=(16, 5))
        ttk.Label(
            dialog,
            text=(
                f"Текущая версия: {CURRENT_VERSION}\n"
                "Проект с открытым исходным кодом."
            ),
            justify=tk.CENTER,
        ).pack(padx=20, pady=(0, 2))

        repository_link = tk.Label(
            dialog,
            text="GitHub: vanitoo/Container-Scan",
            fg="#0969da",
            cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        )
        repository_link.pack(padx=20, pady=(0, 14))
        repository_link.bind(
            "<Button-1>",
            lambda _event: webbrowser.open_new_tab(self.REPOSITORY_URL),
        )

        buttons = ttk.Frame(dialog)
        buttons.pack(padx=14, pady=(0, 14), fill=tk.X)
        ttk.Button(
            buttons,
            text="Проверить обновления",
            command=self.check_for_update_manual,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Закрыть",
            command=dialog.destroy,
        ).pack(side=tk.RIGHT)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (
            self.root.winfo_width() - dialog.winfo_width()
        ) // 2
        y = self.root.winfo_y() + (
            self.root.winfo_height() - dialog.winfo_height()
        ) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

    def show_version_in_title(self):
        self.root.title(f"ContainerScan — версия {CURRENT_VERSION}")

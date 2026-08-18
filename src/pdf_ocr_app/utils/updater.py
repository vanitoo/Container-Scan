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
    UPDATE_SCRIPT = ".container_scan_update.ps1"
    UPDATE_TRACE = "update_trace.log"
    UPDATE_ERROR = "update_error.log"

    def __init__(self, root, add_about_button: bool = True):
        self.root = root
        self.download_cancelled = False
        self.latest_asset = None
        if add_about_button:
            self.add_about_button()
        self.show_version_in_title()
        if getattr(sys, "frozen", False):
            self.root.after(1_000, self._apply_pending_update_on_startup)
            self.root.after(10_000, self.check_for_update_async)

    @property
    def application_dir(self) -> Path:
        return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()

    @property
    def pending_manifest_path(self) -> Path:
        return self.application_dir / self.PENDING_MANIFEST

    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        def normalize(version: str) -> list[int]:
            return [int(part) for part in version.split(".")]
        left, right = normalize(v1), normalize(v2)
        return (left > right) - (left < right)

    def is_newer_version(self, latest: str) -> bool:
        return self.compare_versions(CURRENT_VERSION, latest) < 0

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
            if not download_url.lower().startswith(self.DOWNLOAD_URL_PREFIX.lower()):
                raise ValueError("GitHub Release содержит недоверенный адрес файла обновления")
            logger.info(f"Получена последняя версия: {latest}")
            return latest
        except Exception as exc:
            logger.warning(f"Не удалось получить последнюю версию: {exc}")
            return ""

    def check_for_update_async(self):
        threading.Thread(target=self._check_for_update_worker, daemon=True).start()

    def _check_for_update_worker(self):
        latest = self.get_latest_version()
        if latest and self.is_newer_version(latest):
            logger.info(f"Доступна новая версия {latest}")
            self.root.after(0, lambda: self._show_notification_window(latest))

    def check_for_update_manual(self):
        logger.info("Запущена ручная проверка обновлений")
        threading.Thread(target=self._manual_check_worker, daemon=True).start()

    def _manual_check_worker(self):
        latest = self.get_latest_version()
        self.root.after(0, lambda: self._show_manual_check_result(latest))

    def _show_manual_check_result(self, latest: str):
        if not latest:
            messagebox.showerror(
                "Проверка обновлений",
                "Не удалось получить информацию о последнем релизе.\nПодробности смотрите в логе приложения.",
                parent=self.root,
            )
            return
        if not self.is_newer_version(latest):
            messagebox.showinfo("Проверка обновлений", f"Установлена актуальная версия {CURRENT_VERSION}.", parent=self.root)
            return
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Доступно обновление",
                f"Доступна версия {latest}.\n\nАвтоматическая установка выполняется только из собранного ContainerScan.exe.",
                parent=self.root,
            )
            return
        self._show_notification_window(latest)

    def _show_notification_window(self, latest: str):
        popup = tk.Toplevel(self.root)
        popup.title("Доступно обновление")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.transient(self.root)
        tk.Label(popup, text=f"Доступна новая версия: {latest}", padx=10, pady=10).pack()
        tk.Label(popup, text="Текущая версия будет заменена автоматически.", padx=10).pack()
        buttons = tk.Frame(popup)
        buttons.pack(pady=(0, 10))
        ttk.Button(
            buttons,
            text="Обновить сейчас",
            command=lambda: [popup.destroy(), self.download_update(latest)],
        ).pack(side="left", padx=5)
        ttk.Button(buttons, text="Напомнить позже", command=popup.destroy).pack(side="left", padx=5)
        popup.update_idletasks()
        popup.geometry(
            f"+{popup.winfo_screenwidth() - popup.winfo_width() - 20}"
            f"+{popup.winfo_screenheight() - popup.winfo_height() - 50}"
        )

    def download_update(self, version: str):
        if not getattr(sys, "frozen", False):
            messagebox.showwarning("Обновление", "Автоматическая установка доступна только в ContainerScan.exe.", parent=self.root)
            return
        if not self.latest_asset:
            messagebox.showerror("Ошибка обновления", "Нет проверенных метаданных файла обновления.", parent=self.root)
            return

        url = self.latest_asset["browser_download_url"]
        digest = self.latest_asset["digest"].removeprefix("sha256:").lower()
        expected_size = int(self.latest_asset.get("size", 0))
        window = tk.Toplevel(self.root)
        window.title("Загрузка обновления")
        window.geometry("400x150")
        window.resizable(False, False)
        window.transient(self.root)
        window.grab_set()
        window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - window.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - window.winfo_height()) // 2
        window.geometry(f"+{x}+{y}")
        tk.Label(window, text=f"Загрузка версии {version}", font=("Arial", 12)).pack(pady=10)
        progress = tk.DoubleVar()
        ttk.Progressbar(window, variable=progress, maximum=100, length=350).pack(pady=10)
        status = tk.Label(window, text="Подготовка...")
        status.pack(pady=5)
        ttk.Button(window, text="Отмена", command=lambda: self._cancel_download(window)).pack(pady=5)
        self.download_cancelled = False
        threading.Thread(
            target=self._download_worker,
            args=(url, version, digest, expected_size, progress, status, window),
            daemon=True,
        ).start()

    def _download_worker(self, url, version, expected_digest, expected_size, progress_var, status_label, progress_window):
        exe_path = self.application_dir / f"ContainerScan_{version}.exe"
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            hasher = hashlib.sha256()
            self.root.after(0, lambda: status_label.config(text="Загрузка начата..."))
            with exe_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.download_cancelled:
                        exe_path.unlink(missing_ok=True)
                        self.root.after(0, progress_window.destroy)
                        return
                    if not chunk:
                        continue
                    handle.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = downloaded / total_size * 100
                        text = f"Загружено: {downloaded / 1048576:.1f} MB / {total_size / 1048576:.1f} MB ({percent:.1f}%)"
                        self.root.after(0, lambda value=percent: progress_var.set(value))
                        self.root.after(0, lambda value=text: status_label.config(text=value))
            if expected_size > 0 and downloaded != expected_size:
                raise ValueError(f"Размер обновления не совпадает: ожидалось {expected_size}, получено {downloaded} байт")
            actual_digest = hasher.hexdigest()
            if not hmac.compare_digest(actual_digest, expected_digest):
                raise ValueError("SHA-256 обновления не совпадает с хешем GitHub Release")
            self._write_pending_manifest(version, exe_path, actual_digest)
            logger.info(f"SHA-256 обновления проверен: {actual_digest}")
            logger.info(f"Обновление подготовлено к установке: {exe_path.name}")
            self.root.after(0, lambda: self._download_completed(version, progress_window))
        except Exception as exc:
            exe_path.unlink(missing_ok=True)
            self._clear_pending_manifest()
            self.root.after(0, lambda error=exc: self._download_failed(error, progress_window))

    def _download_completed(self, version: str, progress_window):
        progress_window.destroy()
        logger.info(f"Обновление версии {version} успешно загружено")
        restart = messagebox.askyesno(
            "Обновление загружено",
            f"Версия {version} успешно загружена!\n\nХотите перезапустить приложение для применения обновления?\n\n"
            "Если выберете «Нет», обновление будет автоматически применено при следующем запуске ContainerScan.",
            parent=self.root,
        )
        if restart:
            self._restart_application(version)
        else:
            messagebox.showinfo("Обновление", "Обновление сохранено и будет применено при следующем запуске приложения.", parent=self.root)

    def _download_failed(self, error: Exception, progress_window):
        if progress_window.winfo_exists():
            progress_window.destroy()
        message = f"Ошибка при загрузке обновления: {error}"
        logger.error(message)
        messagebox.showerror("Ошибка обновления", message, parent=self.root)

    def _cancel_download(self, progress_window):
        self.download_cancelled = True
        if progress_window.winfo_exists():
            progress_window.destroy()
        messagebox.showinfo("Отменено", "Загрузка обновления отменена.", parent=self.root)

    def _write_pending_manifest(self, version: str, exe_path: Path, digest: str) -> None:
        data = {"version": version, "file": exe_path.name, "sha256": digest.lower()}
        temp = self.pending_manifest_path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.pending_manifest_path)

    def _clear_pending_manifest(self) -> None:
        self.pending_manifest_path.unlink(missing_ok=True)

    @staticmethod
    def _file_sha256(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _load_valid_pending_update(self) -> tuple[str, Path] | None:
        if not self.pending_manifest_path.is_file():
            return None
        try:
            data = json.loads(self.pending_manifest_path.read_text(encoding="utf-8"))
            version = str(data["version"])
            filename = str(data["file"])
            expected_digest = str(data["sha256"]).lower()
            update_path = (self.application_dir / filename).resolve()
            if update_path.parent != self.application_dir.resolve():
                raise ValueError("Некорректный путь файла отложенного обновления")
            if not update_path.is_file():
                raise FileNotFoundError(f"Файл отложенного обновления не найден: {update_path}")

            if not self.is_newer_version(version):
                logger.info(f"Отложенное обновление {version} больше не требуется")
                self._clear_pending_manifest()
                if getattr(sys, "frozen", False) and update_path != Path(sys.executable).resolve():
                    try:
                        update_path.unlink(missing_ok=True)
                    except OSError as exc:
                        logger.warning(f"Не удалось удалить старый файл обновления {update_path.name}: {exc}")
                return None

            actual_digest = self._file_sha256(update_path)
            if not hmac.compare_digest(actual_digest, expected_digest):
                raise ValueError("SHA-256 отложенного обновления не совпадает с сохранённым значением")
            return version, update_path
        except Exception as exc:
            logger.error(f"Отложенное обновление повреждено или недействительно: {exc}")
            self._clear_pending_manifest()
            return None

    def _apply_pending_update_on_startup(self):
        pending = self._load_valid_pending_update()
        if pending is not None:
            version, _ = pending
            logger.info(f"Найдено отложенное обновление {version}; запускается установка")
            self._restart_application(version)

    def _restart_application(self, version: str):
        try:
            if not getattr(sys, "frozen", False):
                raise RuntimeError("Автоматическая замена доступна только для собранного EXE")
            pending = self._load_valid_pending_update()
            if pending is None:
                raise FileNotFoundError("Подготовленное обновление не найдено или не прошло проверку")
            pending_version, source = pending
            if pending_version != version:
                raise ValueError(f"Ожидалась версия {version}, подготовлена {pending_version}")

            target = Path(sys.executable).resolve()
            script_path = target.parent / self.UPDATE_SCRIPT
            trace_path = target.parent / self.UPDATE_TRACE
            error_path = target.parent / self.UPDATE_ERROR
            backup_path = target.with_name(f"{target.name}.bak")
            script_path.write_text(self._powershell_helper(), encoding="utf-8")

            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            env = os.environ.copy()
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            subprocess.Popen(
                [
                    "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                    "-File", str(script_path),
                    "-ParentProcessId", str(os.getpid()),
                    "-Source", str(source),
                    "-Target", str(target),
                    "-Backup", str(backup_path),
                    "-WorkingDirectory", str(target.parent),
                    "-ManifestPath", str(self.pending_manifest_path),
                    "-TracePath", str(trace_path),
                    "-ErrorPath", str(error_path),
                ],
                cwd=str(target.parent),
                creationflags=flags,
                close_fds=True,
                env=env,
            )
            logger.info(
                f"Запущена установка обновления {version}: {source.name} -> {target.name}; "
                f"трассировка: {trace_path.name}"
            )
            self.root.destroy()
        except Exception as exc:
            logger.error(f"Ошибка при запуске установки обновления: {exc}", exc_info=True)
            messagebox.showerror("Ошибка", f"Не удалось перезапустить приложение: {exc}", parent=self.root)

    @staticmethod
    def _powershell_helper() -> str:
        return r'''param(
    [Parameter(Mandatory=$true)][int]$ParentProcessId,
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Target,
    [Parameter(Mandatory=$true)][string]$Backup,
    [Parameter(Mandatory=$true)][string]$WorkingDirectory,
    [Parameter(Mandatory=$true)][string]$ManifestPath,
    [Parameter(Mandatory=$true)][string]$TracePath,
    [Parameter(Mandatory=$true)][string]$ErrorPath
)
$ErrorActionPreference = "Stop"
function Write-Trace([string]$Message) {
    Add-Content -LiteralPath $TracePath -Value "$(Get-Date -Format o) $Message" -Encoding UTF8
}
try {
    Remove-Item -LiteralPath $ErrorPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Backup -Force -ErrorAction SilentlyContinue
    "" | Set-Content -LiteralPath $TracePath -Encoding UTF8
    Write-Trace "Updater helper started. PID=$PID ParentPID=$ParentProcessId"
    Write-Trace "Source: $Source"
    Write-Trace "Target: $Target"

    for ($wait = 1; $wait -le 400; $wait++) {
        if (-not (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue)) {
            Write-Trace "Application process exited after $wait checks."
            break
        }
        if ($wait -eq 400) { Write-Trace "Parent PID still visible; switching to file-lock retries." }
        Start-Sleep -Milliseconds 250
    }

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Update source does not exist: $Source" }

    $replaced = $false
    $lastReplaceError = ""
    for ($attempt = 1; $attempt -le 120; $attempt++) {
        try {
            if ((Test-Path -LiteralPath $Target -PathType Leaf) -and -not (Test-Path -LiteralPath $Backup -PathType Leaf)) {
                Copy-Item -LiteralPath $Target -Destination $Backup -Force
                Write-Trace "Backup created: $Backup"
            }
            Copy-Item -LiteralPath $Source -Destination $Target -Force
            $replaced = $true
            Write-Trace "Executable replaced successfully on attempt $attempt."
            break
        } catch {
            $lastReplaceError = $_.Exception.Message
            Write-Trace "Replace attempt $attempt failed: $lastReplaceError"
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $replaced) { throw "Could not replace executable. Last error: $lastReplaceError" }

    Write-Trace "Starting updated application..."
    $newProcess = Start-Process -FilePath $Target -WorkingDirectory $WorkingDirectory -PassThru
    Start-Sleep -Seconds 3
    $newProcess.Refresh()
    if ($newProcess.HasExited) {
        Write-Trace "Updated process exited immediately with code $($newProcess.ExitCode)."
        if (Test-Path -LiteralPath $Backup -PathType Leaf) {
            Copy-Item -LiteralPath $Backup -Destination $Target -Force
            Write-Trace "Rollback completed from backup."
        }
        throw "Updated application exited immediately. Rollback was attempted."
    }

    Write-Trace "Updated process started successfully. PID=$($newProcess.Id)"
    Remove-Item -LiteralPath $ManifestPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Source -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Backup -Force -ErrorAction SilentlyContinue
    Write-Trace "Update completed successfully."
} catch {
    $message = $_.Exception.Message
    Write-Trace "ERROR: $message"
    "$(Get-Date -Format o) $message" | Set-Content -LiteralPath $ErrorPath -Encoding UTF8
    exit 1
} finally {
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
'''

    def add_about_button(self):
        ttk.Button(self.root, text="О программе", command=self.show_about).pack(anchor="ne", padx=10, pady=10)

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
        ttk.Label(dialog, text="ContainerScan", font=("Segoe UI Semibold", 13)).pack(padx=20, pady=(16, 5))
        ttk.Label(
            dialog,
            text=f"Текущая версия: {CURRENT_VERSION}\nПроект с открытым исходным кодом.",
            justify=tk.CENTER,
        ).pack(padx=20, pady=(0, 2))
        link = tk.Label(dialog, text="GitHub: vanitoo/Container-Scan", fg="#0969da", cursor="hand2", font=("Segoe UI", 9, "underline"))
        link.pack(padx=20, pady=(0, 14))
        link.bind("<Button-1>", lambda _event: webbrowser.open_new_tab(self.REPOSITORY_URL))
        buttons = ttk.Frame(dialog)
        buttons.pack(padx=14, pady=(0, 14), fill=tk.X)
        ttk.Button(buttons, text="Проверить обновления", command=self.check_for_update_manual).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Закрыть", command=dialog.destroy).pack(side=tk.RIGHT)
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

    def show_version_in_title(self):
        self.root.title(f"ContainerScan — версия {CURRENT_VERSION}")

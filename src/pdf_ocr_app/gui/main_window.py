# gui/main_window.py
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from PIL import Image

from pdf_ocr_app.config import WINDOW_SIZE
from pdf_ocr_app.gui.components import CanvasComponent, StatusBar, TableComponent, TextRedirector
from pdf_ocr_app.gui.themes import apply_minimal_theme, toggle_theme
from pdf_ocr_app.utils.logger import logger
from pdf_ocr_app.utils.updater import AutoUpdater


class MainWindow:
    def __init__(self, app):
        self.app = app
        self.state = app.state
        self.root = None
        self.components = {}

    def prev_page(self):
        """Переход к предыдущей странице"""
        if self.app.pdf_service.prev_page() and self.app.pdf_service.create_display_image():
            self.components['canvas'].display_image()
            self._update_table_selection(self.state.current_page)
            self.components['status'].update_status(
                page=self.state.current_page + 1,
                total=self.state.total_pages,
                msg=f"Страница {self.state.current_page + 1}"
            )
        else:
            messagebox.showinfo("Информация", "Это первая страница")

    def next_page(self):
        """Переход к следующей странице"""
        if self.app.pdf_service.next_page() and self.app.pdf_service.create_display_image():
            self.components['canvas'].display_image()
            self._update_table_selection(self.state.current_page)
            self.components['status'].update_status(
                page=self.state.current_page + 1,
                total=self.state.total_pages,
                msg=f"Страница {self.state.current_page + 1}"
            )
        else:
            messagebox.showinfo("Информация", "Это последняя страница")

    def rotate_page(self, degrees: int):
        """Rotate the current page 90 degrees and refresh its preview."""
        if not self.state.pdf_doc:
            messagebox.showwarning("Нет документа", "Сначала выберите PDF-файл.")
            return

        if (
            self.app.pdf_service.rotate_current_page(degrees)
            and self.app.pdf_service.create_display_image()
        ):
            self.state.cropped_image = None
            canvas = self.components["canvas"]
            canvas.display_image()
            canvas.canvas2.delete("all")
            direction = "вправо" if degrees > 0 else "влево"
            self.components["status"].update_status(
                page=self.state.current_page + 1,
                total=self.state.total_pages,
                msg=f"Страница повернута {direction} на 90°",
            )
            return

        messagebox.showerror("Ошибка", "Не удалось повернуть текущую страницу.")

    def analyze_layout(self):
        """Align the current page to the reference form and transfer its selected area."""
        if (
            not self.state.pdf_doc
            or not self.state.original_page_image
            or not self.state.layout_reference_image
            or not self.state.layout_reference_box
        ):
            messagebox.showwarning("Нет документа", "Сначала выберите PDF-файл.")
            return

        self.btn_analyze_layout.config(state=tk.DISABLED)
        self.components["status"].update_status(msg="Геометрическое сопоставление страницы...")
        reference_image = self.state.layout_reference_image.copy()
        reference_box = self.state.layout_reference_box
        page_image = self.state.original_page_image.copy()
        threading.Thread(
            target=self._analyze_layout_worker,
            args=(reference_image, page_image, reference_box),
            daemon=True,
        ).start()

    def _analyze_layout_worker(self, reference_image, page_image, reference_box):
        try:
            result = self.app.pdf_service.align_area_to_reference(
                reference_image,
                page_image,
                reference_box,
            )
            self.root.after(0, self._apply_layout_analysis, result)
        except Exception as e:
            logger.error(f"Ошибка анализа разметки: {e}", exc_info=True)
            self.root.after(0, self._layout_analysis_failed, str(e))

    def _apply_layout_analysis(self, result):
        self.btn_analyze_layout.config(state=tk.NORMAL)
        if not result:
            self.components["status"].update_status(msg="Не удалось сопоставить разметку страницы")
            messagebox.showwarning(
                "Анализ разметки",
                "Не удалось геометрически сопоставить текущую страницу с первой страницей PDF.",
            )
            return

        x1, y1, x2, y2 = result["box"]
        scale = self.state.scale_factor
        self.state.x_start = round(x1 * scale)
        self.state.y_start = round(y1 * scale)
        self.state.x_end = round(x2 * scale)
        self.state.y_end = round(y2 * scale)

        image_width, image_height = self.state.original_page_image.size
        self.state.selection_rect_norm = (
            x1 / image_width,
            y1 / image_height,
            x2 / image_width,
            y2 / image_height,
        )
        self.state.selected_areas = [
            (
                self.state.rect_id,
                self.state.x_start,
                self.state.y_start,
                self.state.x_end,
                self.state.y_end,
            )
        ]
        self.components["canvas"].draw_selection()
        self.components["status"].update_status(
            msg=f"Область перенесена по разметке ({result['inliers']} совпадений)"
        )
        logger.info(
            f"Анализ разметки: {result['inliers']}/{result['matches']} геометрических совпадений, координаты canvas "
            f"{self.state.x_start},{self.state.y_start},{self.state.x_end},{self.state.y_end}"
        )

    def _layout_analysis_failed(self, error: str):
        self.btn_analyze_layout.config(state=tk.NORMAL)
        self.components["status"].update_status(msg="Ошибка анализа разметки")
        messagebox.showerror("Анализ разметки", f"Не удалось выполнить анализ: {error}")

    def _capture_layout_reference(self):
        """Store the first rendered page and its configured selection as a layout reference."""
        if not self.state.original_page_image or self.state.scale_factor <= 0:
            return

        inverse_scale = 1 / self.state.scale_factor
        self.state.layout_reference_image = self.state.original_page_image.copy()
        self.state.layout_reference_box = (
            round(self.state.x_start * inverse_scale),
            round(self.state.y_start * inverse_scale),
            round(self.state.x_end * inverse_scale),
            round(self.state.y_end * inverse_scale),
        )
        logger.info(
            "Сохранён эталон разметки первой страницы: "
            f"{self.state.layout_reference_box}"
        )

    def _load_and_display_page(self):
        """Загрузка и отображение текущей страницы"""
        try:
            # Загружаем страницу
            if self.app.pdf_service.load_page() and self.app.pdf_service.create_display_image():
                # Отображаем изображение
                self.components['canvas'].display_image()

                # Обновляем статус
                self.components['status'].update_status(
                    page=self.state.current_page + 1,
                    total=self.state.total_pages,
                    msg=f"Страница {self.state.current_page + 1}"
                )

                # Обновляем таблицу БЕЗ вызова goto_page (чтобы избежать рекурсии)
                self._update_table_selection(self.state.current_page)

                logger.debug(f"Успешно перешли на страницу {self.state.current_page + 1}")
            else:
                logger.error("Не удалось загрузить страницу")
        except Exception as e:
            logger.error(f"Ошибка при загрузке страницы: {e}")

    def goto_page_from_table(self, page_num):
        """Переход на страницу из таблицы"""
        try:
            # Проверяем, не пытаемся ли мы перейти на ту же страницу
            if (self.state.current_page == page_num or
                    not self.state.pdf_doc or
                    page_num < 0 or
                    page_num >= self.state.pdf_doc.page_count):
                return

            # Устанавливаем текущую страницу
            self.state.current_page = page_num

            # Загружаем и отображаем страницу
            self._load_and_display_page()

        except Exception as e:
            logger.error(f"Ошибка при переходе на страницу {page_num}: {e}")

    def _update_table_selection(self, page_num):
        """Обновление выделения в таблице БЕЗ вызова навигации"""
        try:
            # Устанавливаем флаг программатического выделения
            self._programmatic_selection = True

            # Снимаем текущее выделение
            for item in self.tree.selection():
                self.tree.selection_remove(item)

            # Выделяем строку соответствующей страницы
            if page_num < len(self.state.table_entries):
                item_id = self.state.table_entries[page_num]["item_id"]
                self.tree.selection_set(item_id)
                self.tree.focus(item_id)
                self.tree.see(item_id)

        except Exception as e:
            logger.error(f"Ошибка обновления выделения таблицы: {e}")
        finally:
            # Сбрасываем флаг
            self._programmatic_selection = False

    def create_interface(self):
        self.root = tk.Tk()
        self.root.withdraw()  # <- спрятали окно на время инициализации
        self.root.title(f"ContainerScan — версия {self.app.version}")
        resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
        icon_path = resource_root / "icon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(default=str(icon_path))
            except tk.TclError as exc:
                logger.warning("Не удалось установить иконку приложения %s: %s", icon_path, exc)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Центрирование окна
        window_width, window_height = WINDOW_SIZE
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = (sw - window_width) // 2
        y = (sh - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Применение темы
        apply_minimal_theme(self.root, self.state.current_theme)

        # Создание компонентов
        self._create_top_toolbar()
        self._create_main_toolbar()
        self._create_extra_toolbar()
        self._create_canvas_area()
        self._create_statusbar()
        self._create_log_area()

        self.root.deiconify()

        # Инициализация координат по умолчанию
        default_coords = f"{self.state.x_start},{self.state.y_start},{self.state.x_end},{self.state.y_end}"
        self.coordinates_entry.delete(0, tk.END)
        self.coordinates_entry.insert(0, default_coords)


        # Настройка логирования
        self._setup_logging()

        # Инициализация автоОбновления
        self.updater = AutoUpdater(self.root, add_about_button=False)

    def _create_top_toolbar(self):
        frame_top = ttk.Frame(self.root, style="Toolbar.TFrame")
        frame_top.pack(side=tk.TOP, fill="x")
        frame_top.grid_columnconfigure(2, weight=1)

        btn_select_pdf = ttk.Button(frame_top, text="Выбрать PDF", command=self.select_pdf)
        btn_load_registry = ttk.Button(frame_top, text="Выбрать XLS", command=self.load_registry)
        self.entry_pdf_path = ttk.Entry(frame_top)
        btn_recognize = ttk.Button(frame_top, text="Запуск распознавания", command=self.start_recognition_thread)
        btn_match = ttk.Button(frame_top, text="Сопоставить", command=self.match_with_expected)
        btn_save = ttk.Button(frame_top, text="Сохранить результаты", command=lambda: self.save_results(btn_save))

        btn_select_pdf.grid(row=0, column=0, padx=6, pady=8, sticky="w")
        btn_load_registry.grid(row=0, column=1, padx=6, pady=8, sticky="w")
        self.entry_pdf_path.grid(row=0, column=2, padx=6, pady=8, sticky="we")
        btn_recognize.grid(row=0, column=3, padx=6, pady=8, sticky="e")
        btn_match.grid(row=0, column=4, padx=6, pady=8, sticky="e")
        btn_save.grid(row=0, column=5, padx=6, pady=8, sticky="e")

        ttk.Separator(self.root, orient="horizontal").pack(side=tk.TOP, fill="x")

    def _create_main_toolbar(self):
        frame_main = ttk.Frame(self.root)
        frame_main.pack(pady=6, padx=10, fill="x")

        frame_left = ttk.Frame(frame_main)
        frame_left.pack(side=tk.LEFT, fill="x", expand=False)

        button_width = 16
        btn_prev = ttk.Button(frame_left, text="← Назад", command=self.prev_page, width=button_width)
        btn_next = ttk.Button(frame_left, text="Вперед →", command=self.next_page, width=button_width)
        btn_rotate_left = ttk.Button(
            frame_left, text="↶ 90°", command=lambda: self.rotate_page(-90), width=button_width
        )
        btn_rotate_right = ttk.Button(
            frame_left, text="90° ↷", command=lambda: self.rotate_page(90), width=button_width
        )
        self.btn_analyze_layout = ttk.Button(
            frame_left, text="Анализ", command=self.analyze_layout, width=button_width
        )
        btn_check = ttk.Button(frame_left, text="Проверить лист", command=self.check_image, width=button_width)
        btn_save_page = ttk.Button(frame_left, text="Сохранить лист", command=self.save_current_page,
                                   width=button_width)

        btn_prev.pack(side=tk.LEFT, padx=4, pady=2)
        btn_next.pack(side=tk.LEFT, padx=4, pady=2)
        btn_rotate_left.pack(side=tk.LEFT, padx=4, pady=2)
        btn_rotate_right.pack(side=tk.LEFT, padx=4, pady=2)
        self.btn_analyze_layout.pack(side=tk.LEFT, padx=4, pady=2)
        btn_check.pack(side=tk.LEFT, padx=4, pady=2)
        btn_save_page.pack(side=tk.LEFT, padx=4, pady=2)

        ttk.Separator(frame_main, orient="vertical").pack(side=tk.LEFT, fill="y", padx=8)

        # Сохраняем ссылку на frame_main для позиционирования
        self.frame_main = frame_main

        frame_right = ttk.Frame(frame_main)
        frame_right.pack(side=tk.RIGHT, fill=tk.X, expand=False)

        self.extra_mode = tk.BooleanVar(value=False)
        options_btn = ttk.Checkbutton(
            frame_right,
            text="Options",
            variable=self.extra_mode,
            command=self.toggle_extra_options
        )
        options_btn.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            frame_right,
            text="О программе",
            command=lambda: self.updater.show_about(),
        ).pack(side=tk.LEFT, padx=(4, 0))

    def _create_canvas_area(self):
        """Создание области с холстами и таблицей"""
        self.frame_canvases = ttk.Frame(self.root)
        self.frame_canvases.pack(pady=10, padx=10, fill="both", expand=True)

        # Создание компонента canvas
        self.components['canvas'] = CanvasComponent(self.frame_canvases, self.app)
        self.components['canvas'].create_canvases()

        ttk.Separator(self.frame_canvases, orient="vertical").pack(side=tk.LEFT, fill="y", padx=8)

        # Создание компонента таблицы
        self.components['table'] = TableComponent(self.frame_canvases, self.app)
        self.tree = self.components['table'].create_table()

        # Добавляем привязку клавиш навигации
        self.components['table'].bind_navigation_keys()

        # Добавляем ссылку на tree в состояние для доступа из сервисов
        self.state.tree = self.tree
        self.state.gui = self

    def _create_log_area(self):
        self.text_output = scrolledtext.ScrolledText(self.root, height=8)
        self.text_output.pack(side=tk.BOTTOM, fill="x", pady=8, padx=10)
        self.text_output.config(state="normal")

    def _create_statusbar(self):
        self.components['status'] = StatusBar(self.root, self.app)
        self.components['status'].create_statusbar()

    def _setup_logging(self):
        sys.stdout = TextRedirector(self.text_output)
        self.text_output.tag_configure("hyperlink", foreground="blue", underline=True)
        logger.update_gui_handler(self.text_output)

    def run(self):
        self.root.mainloop()

    def select_pdf(self):
        try:
            file_paths = filedialog.askopenfilenames(
                title="Выберите PDF файлы",
                filetypes=[("PDF файлы", "*.pdf"), ("Все файлы", "*.*")]
            )

            if not file_paths:
                return

            if len(file_paths) == 1:
                # Один файл
                file_path = file_paths[0]
                success = self.app.pdf_service.load_pdf(file_path)
                if success:
                    self.entry_pdf_path.delete(0, tk.END)
                    self.entry_pdf_path.insert(0, file_path)

                    # Загружаем и отображаем страницу
                    if self.app.pdf_service.load_page() and self.app.pdf_service.create_display_image():
                        self._capture_layout_reference()
                        self.components["canvas"].show_recognition_result(None)
                        self.components['canvas'].display_image()
                        self._build_table_from_pdf()
                        self.components['status'].update_status(
                            page=1,
                            total=self.state.total_pages,
                            msg=f"Загружен PDF: {Path(file_path).name}"
                        )
                    else:
                        messagebox.showerror("Ошибка", "Не удалось загрузить страницу PDF")
                else:
                    messagebox.showerror("Ошибка", "Не удалось загрузить PDF файл")

            else:
                # Несколько файлов
                success = self.app.pdf_service.process_multiple_pdfs(file_paths)
                if success:
                    self.entry_pdf_path.delete(0, tk.END)
                    file_names = [Path(f).name for f in file_paths[:3]]
                    display_text = f"{', '.join(file_names)}"
                    if len(file_paths) > 3:
                        display_text += f" ... (+{len(file_paths) - 3} файлов)"
                    self.entry_pdf_path.insert(0, display_text)

                    # Загружаем и отображаем страницу
                    if self.app.pdf_service.load_page() and self.app.pdf_service.create_display_image():
                        self._capture_layout_reference()
                        self.components["canvas"].show_recognition_result(None)
                        self.components['canvas'].display_image()
                        self._build_table_from_pdf()
                        self.components['status'].update_status(
                            page=1,
                            total=self.state.total_pages,
                            msg=f"Загружено {len(file_paths)} PDF файлов"
                        )
                    else:
                        messagebox.showerror("Ошибка", "Не удалось загрузить страницу PDF")
                else:
                    messagebox.showerror("Ошибка", "Не удалось обработать PDF файлы")

        except Exception as e:
            logger.error(f"Ошибка при выборе PDF: {e}")
            messagebox.showerror("Ошибка", f"Ошибка при выборе PDF: {e}")

    def _build_table_from_pdf(self):
        """Построение таблицы на основе загруженного PDF"""
        if not self.state.pdf_doc:
            return

        # Очищаем таблицу
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.state.table_entries = []

        # Создаем строки по количеству страниц
        for i in range(self.state.pdf_doc.page_count):
            item_id = self.tree.insert(
                "",
                tk.END,
                values=(
                    i + 1,  # № страницы
                    "",  # Контейнер из XLS
                    "",  # invoice (накладная из XLS)
                    "",  # Распознанный контейнер
                    "",  # Совпадение
                    "",  # Коэффициент
                    "",  # Различия распознанного и сопоставленного кодов
                ),
            )
            self.state.table_entries.append({
                "index": i + 1,
                "item_id": item_id,
                "code": "",
                "recognized": "",
                "xls_id": ""
            })

        self.components["table"].update_match_summary()

        logger.info(f"Построена таблица для {self.state.pdf_doc.page_count} страниц")

    def load_registry(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel or CSV", "*.xlsx *.csv")])
        if file_path:
            try:
                records = self.app.excel_service.read_registry(file_path)
                self.apply_registry_records(records)
            except Exception as e:
                logger.error(f"Ошибка при выборе реестра: {e}")
                messagebox.showerror("Ошибка", f"Не удалось загрузить реестр: {e}")

    def start_recognition_thread(self):
        threading.Thread(target=self.start_recognition, daemon=True).start()

    def match_with_expected(self):
        expected_containers = [container for _, container in self.state.all_excel_records if container]
        match_results = self.app.matching_service.match_entries(self.state.table_entries, expected_containers)
        self.apply_match_results(match_results)

    def apply_registry_records(self, records):
        """Применение загруженных записей реестра к таблице GUI."""
        self.state.all_excel_records = records
        self.state.expected_containers = [container for _, container in records if container]

        if not getattr(self, "tree", None) or not self.state.table_entries:
            return

        for entry in self.state.table_entries:
            entry["code"] = ""
            entry["xls_id"] = ""
            item_id = entry["item_id"]
            values = list(self.tree.item(item_id, "values"))
            while len(values) < 6:
                values.append("")
            values[1] = ""
            values[2] = ""
            self.tree.item(item_id, values=tuple(values))

        updated_rows = min(len(records), len(self.state.table_entries))
        for i in range(updated_rows):
            xls_id, code = records[i]
            self.state.table_entries[i]["code"] = code
            self.state.table_entries[i]["xls_id"] = xls_id

            item_id = self.state.table_entries[i]["item_id"]
            current_values = list(self.tree.item(item_id, "values"))
            while len(current_values) < 6:
                current_values.append("")

            current_values[1] = code
            current_values[2] = xls_id
            self.tree.item(item_id, values=tuple(current_values))

    def apply_match_results(self, match_results):
        """Применение результатов сопоставления к таблице GUI."""
        if not getattr(self, "tree", None) or not self.state.table_entries:
            return

        for entry in self.state.table_entries:
            item_id = entry["item_id"]
            values = list(self.tree.item(item_id, "values"))
            while len(values) < 6:
                values.append("")
            values[4] = ""
            values[5] = ""
            while len(values) < 7:
                values.append("")
            values[6] = ""
            self.tree.item(item_id, values=tuple(values), tags=())

        if not match_results:
            self.components["table"].update_match_summary()
            return

        self.tree.tag_configure("exact_match", background="#a8e6a8")
        self.tree.tag_configure("partial_match", background="#fff8a8")
        self.tree.tag_configure("no_match", background="#ffaaaa")

        for result in match_results:
            item_id = result.get("item_id")
            if not item_id:
                continue

            values = list(self.tree.item(item_id, "values"))
            while len(values) < 6:
                values.append("")

            values[4] = result.get("best_match", "")
            values[5] = f'{result.get("best_score", 0.0):.2f}'
            while len(values) < 7:
                values.append("")
            values[6] = self.components["table"].format_differences(
                values[3], values[4]
            )
            self.tree.item(item_id, values=tuple(values), tags=(result.get("tag", "no_match"),))

        self.components["table"].update_match_summary()

    def save_results(self, btn):
        btn.config(state=tk.DISABLED)
        threading.Thread(target=self._save_results_worker, args=(btn,), daemon=True).start()

    def _show_save_summary(self, output_dir: Path, message: str, has_errors: bool):
        """Show save totals with a button that opens the result directory."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Сохранение завершено с ошибками" if has_errors else "Сохранено")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text=message,
            justify=tk.LEFT,
            padding=(16, 14),
        ).pack(fill=tk.BOTH, expand=True)

        buttons = ttk.Frame(dialog)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))

        def open_results_folder():
            try:
                os.startfile(str(output_dir.resolve()))
            except Exception as error:
                messagebox.showerror(
                    "Ошибка",
                    f"Не удалось открыть папку:\n{error}",
                    parent=dialog,
                )

        ttk.Button(buttons, text="ОК", command=dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Открыть папку", command=open_results_folder).pack(
            side=tk.RIGHT, padx=(0, 6)
        )
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _save_results_worker(self, btn):
        """Рабочий процесс сохранения всех результатов с окном прогресса."""
        try:
            # Быстрые проверки — все UI-действия только через after
            if not self.state.pdf_doc:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", "PDF документ не загружен"))
                self.root.after(0, lambda: btn.config(state=tk.NORMAL))
                return

            if not self.state.table_entries:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", "Нет данных для сохранения"))
                self.root.after(0, lambda: btn.config(state=tk.NORMAL))
                return

            # Данные прогресса/окна
            ui = {"win": None, "bar": None, "var": None, "lab": None}

            def _open_progress():
                # Создаём окно прогресса в главном потоке
                progress = tk.Toplevel(self.root)
                progress.title("Сохранение...")
                progress.resizable(False, False)
                w, h = 360, 120
                try:
                    self.root.update_idletasks()
                    x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
                    y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
                    progress.geometry(f"{w}x{h}+{x}+{y}")
                except Exception:
                    progress.geometry(f"{w}x{h}")

                progress.transient(self.root)

                ttk.Label(progress, text="Идёт сохранение результатов").pack(pady=(14, 6))

                ui["var"] = tk.DoubleVar(value=0.0)
                bar = ttk.Progressbar(progress, mode="determinate", maximum=100.0, variable=ui["var"])
                bar.pack(fill="x", padx=18)
                ui["bar"] = bar

                ui["lab"] = tk.StringVar(value="")
                ttk.Label(progress, textvariable=ui["lab"]).pack(pady=(6, 10))

                ui["win"] = progress

            def _update_progress(percent: float, text: str):
                if ui.get("var") is not None:
                    ui["var"].set(percent)
                if ui.get("lab") is not None:
                    ui["lab"].set(text)

            def _close_progress_ok(output_dir: Path, saved_count: int, failed_pages: list[int], total: int):
                try:
                    if ui.get("win"):
                        ui["win"].destroy()
                finally:
                    failed_count = len(failed_pages)
                    message = (
                        f"Успешно сохранено листов: {saved_count} из {total}\n"
                        f"Ошибок сохранения: {failed_count}\n\n"
                        f"Папка:\n{output_dir}"
                    )
                    if failed_pages:
                        message += "\n\nНе сохранены страницы: " + ", ".join(map(str, failed_pages))
                    self._show_save_summary(output_dir, message, bool(failed_pages))
                    btn.config(state=tk.NORMAL)

            def _close_progress_err(msg: str):
                try:
                    if ui.get("win"):
                        ui["win"].destroy()
                finally:
                    messagebox.showerror("Ошибка", msg)
                    btn.config(state=tk.NORMAL)

            # Открываем окно прогресса
            self.root.after(0, _open_progress)

            # Куда сохраняем: рядом с текущим (возможно объединённым) PDF
            output_dir = Path(self.state.pdf_path).parent

            total = len(self.state.table_entries)
            saved_count = 0
            failed_pages = []
            for i, entry in enumerate(self.state.table_entries):
                try:
                    page_num = entry["index"] - 1
                    page = self.state.pdf_doc.load_page(page_num)
                    pix = page.get_pixmap(dpi=200)
                    page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                    # --- Имя: match -> recognized -> page_{i+1}
                    row_values = list(self.tree.item(entry["item_id"], "values"))

                    # match из таблицы (колонка 4 — "Контейнер распознанный" у вас ранее была на #4)
                    match_cell = (row_values[4] if len(row_values) > 4 and row_values[4] else "").strip()

                    # recognized: сперва из entry (если есть), иначе из таблицы (обычно колонка 3)
                    recognized_cell_in_table = (row_values[3] if len(row_values) > 3 and row_values[3] else "").strip()
                    recognized = (entry.get("recognized") or recognized_cell_in_table or "").strip()

                    basename = match_cell or recognized or f"page_{i + 1}"

                    # --- Ищем накладную по expected == (match|recognized)
                    invoice_prefix = ""
                    search_key = (match_cell or recognized).strip()
                    if search_key:
                        for e in self.state.table_entries:
                            vals = list(self.tree.item(e["item_id"], "values"))
                            expected_val = (vals[1] if len(vals) > 1 and vals[1] else "").strip()
                            if expected_val == search_key:
                                invoice_prefix = (e.get("xls_id") or (vals[2] if len(vals) > 2 else "") or "").strip()
                                if invoice_prefix:
                                    break

                    # --- Итоговое имя
                    filename = f"{invoice_prefix}_{basename}" if invoice_prefix else basename
                    output_file = output_dir / filename

                    # Сохраняем основное изображение
                    page_image.save(f"{output_file}.jpg")
                    saved_count += 1

                    # Debug-дампы: кроп и _info.txt
                    if self.state.debug_mode:
                        # возможный кроп из текущей сессии
                        cropped = getattr(self.state, "cropped_image", None)
                        if cropped is not None:
                            try:
                                cropped.save(f"{output_file}_cropped.jpg")
                            except Exception as e_crop:
                                logger.error(f"Не удалось сохранить вырезку: {e_crop}", exc_info=True)

                        # _info.txt при наличии результата распознавания
                        if i < len(self.state.recognition_results):
                            try:
                                result = self.state.recognition_results[i]
                                info_path = Path(f"{output_file}_info.txt")
                                with info_path.open("w", encoding="utf-8") as f:
                                    f.write(f"Страница: {result.get('page')}\n")
                                    f.write(f"Координаты: {result.get('coords')}\n")
                                    f.write(f"Движок OCR: {result.get('engine')}\n")
                                    f.write("\n--- Исходный текст ---\n")
                                    f.write(result.get('raw_text', ""))
                                    f.write("\n\n--- Форматированный текст ---\n")
                                    f.write(result.get('formatted_text', ""))
                            except Exception as e_info:
                                logger.error(f"Не удалось сохранить _info.txt: {e_info}", exc_info=True)

                except Exception as page_err:
                    failed_pages.append(i + 1)
                    logger.error(f"Не удалось сохранить страницу {i + 1}: {page_err}", exc_info=True)

                # Обновление прогресса (в главном потоке)
                percent = ((i + 1) / max(1, total)) * 100.0
                text = f"{i + 1} из {total}"
                self.root.after(0, _update_progress, percent, text)

            # Закрываем окно прогресса — успех
            self.root.after(
                0,
                lambda d=output_dir, saved=saved_count, failed=failed_pages, count=total:
                    _close_progress_ok(d, saved, failed, count),
            )

        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}", exc_info=True)
            # Закрываем окно прогресса — ошибка
            self.root.after(0, lambda error=e: _close_progress_err(f"Ошибка при сохранении: {error!s}"))

    def _save_results_completed(self, btn, output_dir):
        """Завершение сохранения результатов"""
        btn.config(state=tk.NORMAL)
        messagebox.showinfo("Сохранено", f"Результаты сохранены в папку:\n{output_dir}")

    def _save_results_failed(self, btn, error):
        """Ошибка сохранения результатов"""
        btn.config(state=tk.NORMAL)
        messagebox.showerror("Ошибка", f"Ошибка при сохранении: {error}")

    def check_image(self):
        """Проверка распознавания на текущей странице"""
        if not self.state.pdf_doc:
            messagebox.showwarning("Нет файла", "Пожалуйста, выберите PDF-файл.")
            return

        # Если нет выделенной области, но есть координаты
        if (not self.state.selected_areas and
                all(v is not None for v in
                    [self.state.x_start, self.state.y_start, self.state.x_end, self.state.y_end])):
            self.state.selected_areas = [
                (None, self.state.x_start, self.state.y_start, self.state.x_end, self.state.y_end)]
            self.components['canvas'].draw_selection()

        if not self.state.selected_areas:
            messagebox.showwarning("Нет выделения", "Пожалуйста, выделите область на холсте.")
            return

        try:
            area = self.state.selected_areas[0]
            _, x1, y1, x2, y2 = area
            coords = (x1, y1, x2, y2)

            recognized_text = self.app.ocr_service.recognize_area(self.state.current_page, coords)

            # Обновляем таблицу
            if self.state.current_page < len(self.state.table_entries):
                self.state.table_entries[self.state.current_page]["recognized"] = recognized_text
                item_id = self.state.table_entries[self.state.current_page]["item_id"]
                current_values = list(self.tree.item(item_id, "values"))
                current_values[3] = recognized_text
                self.tree.item(item_id, values=current_values)

            # Выводим в лог
            if self.state.current_page < len(self.state.recognition_results):
                result = self.state.recognition_results[self.state.current_page]
                logger.info(f"=== Страница {self.state.current_page + 1} ===")
                logger.info(f"Координаты: {result['coords']}")
                logger.info(f"Движок: {result['engine']}")
                logger.info("\n--- Исходный текст ---")
                logger.info(result["raw_text"])
                logger.info("\n--- Форматированный текст ---")
                logger.info(result["formatted_text"])
                self.components["canvas"].show_recognition_result(result)

            messagebox.showinfo("Успех", f"Страница {self.state.current_page + 1} распознана: {recognized_text}")

        except Exception as e:
            logger.error(f"Ошибка при распознавании страницы {self.state.current_page + 1}: {e}")
            messagebox.showerror("Ошибка", f"Ошибка при распознавании: {e}")

    def save_current_page(self):
        """Сохранение текущей страницы как изображения"""
        if not self.state.pdf_path:
            messagebox.showerror("Ошибка", "Не выбран PDF файл.")
            return

        try:
            page = self.state.pdf_doc.load_page(self.state.current_page)
            pix = page.get_pixmap(dpi=200)
            page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Получаем данные для имени файла
            row_values = list(self.tree.item(
                self.state.table_entries[self.state.current_page]["item_id"], "values"
            ))

            match_cell = (row_values[4] if len(row_values) > 4 and row_values[4] else "").strip()
            recognized = (self.state.table_entries[self.state.current_page].get("recognized") or "").strip()
            basename = match_cell or recognized or f"page_{self.state.current_page + 1}"

            # Ищем накладную
            invoice_prefix = ""
            search_key = (match_cell or recognized).strip()
            if search_key:
                for entry in self.state.table_entries:
                    vals = list(self.tree.item(entry["item_id"], "values"))
                    expected_val = (vals[1] if len(vals) > 1 and vals[1] else "").strip()
                    if expected_val == search_key:
                        invoice_prefix = (entry.get("xls_id") or (vals[2] if len(vals) > 2 else "") or "").strip()
                        if invoice_prefix:
                            break

            # Формируем имя файла
            filename = f"{invoice_prefix}_{basename}" if invoice_prefix else basename
            output_dir = Path(self.state.pdf_path).parent
            output_file = output_dir / f"{self.state.current_page + 1}_{filename}"

            # Сохраняем
            page_image.save(f"{output_file}_full.jpg")

            if self.state.debug_mode and self.state.cropped_image:
                try:
                    self.state.cropped_image.save(f"{output_file}_cropped.jpg")
                except Exception as e:
                    logger.debug(f"Не удалось сохранить обрезанное изображение: {e}")

            messagebox.showinfo("Успех", f"Страница сохранена как {output_file}_full.jpg")

        except Exception as e:
            logger.error(f"Ошибка при сохранении страницы: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить страницу: {e}")



    def update_debug_mode(self):
        dbg = bool(self.debug_mode.get())
        logger.info(f"Debug mode: {dbg}")
        # Дополнительная логика обновления интерфейса

    def toggle_theme(self):
        toggle_theme(self.root)

    def init_ocr_engine(self):
        selected_engine = self.ocr_engine_var.get()
        logger.debug(f"Инициализация OCR движка: {selected_engine}")

    def update_coordinates(self, event=None):
        """Обновление координат из поля ввода"""
        try:
            coordinates = self.coordinates_entry.get().split(",")
            if len(coordinates) == 4:
                self.state.x_start, self.state.y_start, self.state.x_end, self.state.y_end = map(int, coordinates)
                logger.info(
                    "Обновлены координаты: "
                    f"{self.state.x_start}, {self.state.y_start}, "
                    f"{self.state.x_end}, {self.state.y_end}"
                )

                # Обновляем выделение на canvas
                self.components['canvas'].draw_selection()

                # Обновляем выбранные области
                self.state.selected_areas.clear()
                self.state.selected_areas.append((
                    self.state.rect_id,
                    self.state.x_start,
                    self.state.y_start,
                    self.state.x_end,
                    self.state.y_end
                ))
            else:
                logger.warning("Неверный формат координат. Нужно: x1,y1,x2,y2")
        except ValueError as e:
            logger.warning(f"Ошибка формата координат: {e}")

    def on_closing(self):
        # Обработчик закрытия окна
        self.root.destroy()

    def start_recognition(self):
        """Запуск распознавания всех страниц"""
        if not self.state.pdf_doc:
            messagebox.showwarning("Нет документа", "Пожалуйста, выберите PDF-файл.")
            return

        # Если нет выделенной области, но есть координаты
        if (not self.state.selected_areas and
                all(v is not None for v in
                    [self.state.x_start, self.state.y_start, self.state.x_end, self.state.y_end])):
            self.state.selected_areas = [
                (None, self.state.x_start, self.state.y_start, self.state.x_end, self.state.y_end)]
            self.components['canvas'].draw_selection()

        if not self.state.selected_areas:
            messagebox.showwarning("Нет выделения", "Пожалуйста, выделите область на холсте.")
            return

        try:
            # Показываем диалог прогресса
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Распознавание...")
            progress_window.geometry("300x100")
            progress_window.resizable(False, False)
            progress_window.transient(self.root)
            progress_window.grab_set()

            # Центрируем окно
            progress_window.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - progress_window.winfo_width()) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - progress_window.winfo_height()) // 2
            progress_window.geometry(f"+{x}+{y}")

            tk.Label(progress_window, text="Идет распознавание страниц...").pack(pady=10)
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, length=250)
            progress_bar.pack(pady=5)
            progress_bar.start()

            # Запускаем в отдельном потоке
            threading.Thread(
                target=self._recognition_worker,
                args=(progress_var, progress_window),
                daemon=True
            ).start()

        except Exception as e:
            logger.error(f"Ошибка при запуске распознавания: {e}")
            messagebox.showerror("Ошибка", f"Ошибка при запуске распознавания: {e}")

    def _recognition_worker(self, progress_var, progress_window):
        """Рабочий процесс распознавания"""
        try:
            area = self.state.selected_areas[0]
            _, x1, y1, x2, y2 = area
            coords = (x1, y1, x2, y2)

            total_pages = self.state.pdf_doc.page_count

            for page_num in range(total_pages):
                # Обновляем прогресс
                progress = (page_num / total_pages) * 100
                self.root.after(0, lambda p=progress: progress_var.set(p))

                # Fast mass mode uses the same selected coordinates on every page.
                recognized_text = self.app.ocr_service.recognize_area(
                    page_num,
                    coords,
                    use_page_scale=self.state.mass_page_scale,
                )

                # Обновляем таблицу в основном потоке
                self.root.after(0, self._update_table_row, page_num, recognized_text)

            # Завершаем
            self.root.after(0, lambda: self._recognition_completed(progress_window, total_pages))

        except Exception as e:
            logger.error(f"Ошибка в процессе распознавания: {e}")
            self.root.after(0, lambda error=e: self._recognition_failed(progress_window, error))

    def _update_table_row(self, page_num, recognized_text):
        """Обновление строки таблицы"""
        if page_num < len(self.state.table_entries):
            self.state.table_entries[page_num]["recognized"] = recognized_text
            item_id = self.state.table_entries[page_num]["item_id"]
            current_values = list(self.tree.item(item_id, "values"))
            current_values[3] = recognized_text  # recognized column
            self.tree.item(item_id, values=current_values)

        if page_num < len(self.state.recognition_results):
            self.components["canvas"].show_recognition_result(
                self.state.recognition_results[page_num]
            )

    def _recognition_completed(self, progress_window, total_pages):
        """Завершение распознавания"""
        progress_window.destroy()
        messagebox.showinfo("Готово", f"Распознано {total_pages} страниц.")
        logger.info(f"Массовое распознавание завершено: {total_pages} страниц")

    def _recognition_failed(self, progress_window, error):
        """Ошибка распознавания"""
        progress_window.destroy()
        messagebox.showerror("Ошибка", f"Ошибка при распознавании: {error}")

    def _create_extra_toolbar(self):
        """Создание дополнительной панели настроек"""
        self.frame_extra = ttk.Frame(self.root)
        # Изначально не показываем - будет показана при включении Options

        # Содержимое дополнительной панели
        frame_left_extra = ttk.Frame(self.frame_extra)
        frame_left_extra.pack(side=tk.LEFT, fill="x", expand=False)

        self.recognition_mode = tk.IntVar(value=0)
        self.debug_mode = tk.BooleanVar(value=False)
        self.legacy_tesseract = tk.BooleanVar(value=self.state.use_legacy_tesseract)
        self.mass_page_scale = tk.BooleanVar(value=self.state.mass_page_scale)

        adv_checkbutton = ttk.Checkbutton(
            frame_left_extra,
            text="Advance",
            variable=self.recognition_mode,
            command=self._update_recognition_mode
        )
        self.adv_checkbutton = adv_checkbutton
        self.legacy_tesseract_checkbutton = ttk.Checkbutton(
            frame_left_extra,
            text="Старый OCR 2.0.3",
            variable=self.legacy_tesseract,
            command=self._update_legacy_tesseract,
        )
        debug_checkbutton = ttk.Checkbutton(
            frame_left_extra,
            text="Debug",
            variable=self.debug_mode,
            command=self._update_debug_mode
        )
        page_scale_checkbutton = ttk.Checkbutton(
            frame_left_extra,
            text="Масштаб каждого листа",
            variable=self.mass_page_scale,
            command=self._update_mass_page_scale,
        )
        adv_checkbutton.pack(side=tk.LEFT, padx=4)
        self.legacy_tesseract_checkbutton.pack(side=tk.LEFT, padx=4)
        debug_checkbutton.pack(side=tk.LEFT, padx=4)
        page_scale_checkbutton.pack(side=tk.LEFT, padx=4)

        btn_theme = ttk.Button(frame_left_extra, text="Тема", command=self._toggle_theme)
        btn_theme.pack(side=tk.LEFT, padx=6)

        ttk.Separator(self.frame_extra, orient="vertical").pack(side=tk.LEFT, fill="y", padx=8)

        frame_center = ttk.Frame(self.frame_extra)
        frame_center.pack(side=tk.LEFT, fill="x", expand=True)

        ocr_container = ttk.Frame(frame_center)
        ocr_container.pack(fill="x", expand=True)

        ttk.Label(ocr_container, text="OCR движок:").pack(side=tk.LEFT, padx=4)
        self.ocr_engine_var = tk.StringVar(value="Tesseract")
        ocr_options = ["Tesseract", "EasyOCR", "PaddleOCR"]
        ocr_menu = ttk.Combobox(
            ocr_container,
            textvariable=self.ocr_engine_var,
            values=ocr_options,
            state="readonly",
            width=16
        )
        ocr_menu.pack(side=tk.LEFT, padx=4)

        ttk.Button(
            ocr_container,
            text="Инициализировать",
            command=self._init_ocr_engine
        ).pack(side=tk.LEFT, padx=4)

        ttk.Separator(self.frame_extra, orient="vertical").pack(side=tk.LEFT, fill="y", padx=8)

        frame_right = ttk.Frame(self.frame_extra)
        frame_right.pack(side=tk.RIGHT, fill="x", expand=False)

        ttk.Label(frame_right, text="Шаблон:").pack(side=tk.LEFT, padx=4)
        self.regex_pattern_entry = ttk.Entry(frame_right, width=28)
        self.regex_pattern_entry.pack(side=tk.LEFT, padx=4)
        self.regex_pattern_entry.insert(0, self.state.regex_pattern)

        ttk.Label(frame_right, text="Координаты:").pack(side=tk.LEFT, padx=4)
        self.coordinates_entry = ttk.Entry(frame_right, width=22)
        self.coordinates_entry.pack(side=tk.LEFT, padx=4)

        # Устанавливаем начальные координаты
        default_coords = f"{self.state.x_start},{self.state.y_start},{self.state.x_end},{self.state.y_end}"
        self.coordinates_entry.delete(0, tk.END)
        self.coordinates_entry.insert(0, default_coords)
        self.coordinates_entry.bind("<KeyRelease>", self._update_coordinates)

    def toggle_extra_options(self):
        """Переключение видимости дополнительной панели"""
        if self.extra_mode.get():
            # Показываем панель
            if not self.frame_extra.winfo_ismapped():
                self.frame_extra.pack(fill="x", padx=10, pady=5, before=self.frame_canvases)
        else:
            # Скрываем панель
            if self.frame_extra.winfo_ismapped():
                self.frame_extra.pack_forget()

    def _update_recognition_mode(self):
        """Обновление режима распознавания"""
        self.state.recognition_mode = self.recognition_mode.get()
        mode_text = "Advance" if self.state.recognition_mode == 1 else "Basic"
        logger.info(f"Режим распознавания изменен на: {mode_text}")
        self.legacy_tesseract_checkbutton.config(
            state=tk.DISABLED if self.state.recognition_mode == 1 else tk.NORMAL
        )
        if self.state.recognition_mode == 1:
            self._show_advanced_settings()

    def _update_legacy_tesseract(self):
        self.state.use_legacy_tesseract = self.legacy_tesseract.get()
        mode = "старый 2.0.3" if self.state.use_legacy_tesseract else "новый"
        logger.info(f"Базовый алгоритм Tesseract: {mode}")

    def _show_advanced_settings(self):
        """Show configurable OCR preprocessing stages and their execution order."""
        existing = getattr(self, "advanced_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return

        window = tk.Toplevel(self.root)
        self.advanced_window = window
        window.title("Настройки Advance OCR")
        window.resizable(False, False)
        ttk.Label(
            window,
            text="Этапы выполняются сверху вниз. Выберите этап и меняйте порядок.",
        ).grid(row=0, column=0, columnspan=6, padx=10, pady=(10, 6), sticky="w")

        names = {
            "grayscale": "Оттенки серого",
            "median_blur": "Медианное размытие",
            "clahe": "Контраст CLAHE",
            "thresholding": "Бинаризация Otsu",
            "resize": "Увеличение",
            "deskew": "Выравнивание наклона",
            "noise_removal": "Удаление шума",
            "morphological_ops": "Морфология",
        }
        stages = tk.Listbox(window, width=27, height=8, exportselection=False)
        stages.grid(row=1, column=0, rowspan=9, padx=(10, 6), pady=4, sticky="ns")
        for key in self.state.advanced_order:
            stages.insert(tk.END, names[key])
        stages.selection_set(0)

        enabled_vars = {}
        value_vars = {}
        specs = {
            "median_blur": [("kernel", "Ядро", 3, 15, 2)],
            "clahe": [("clip_limit", "Сила", 0.1, 10.0, 0.1), ("grid_size", "Сетка", 1, 32, 1)],
            "resize": [("factor", "Масштаб", 0.5, 5.0, 0.25)],
            "noise_removal": [("kernel", "Ядро", 3, 15, 2)],
            "morphological_ops": [("kernel", "Ядро", 1, 9, 1), ("iterations", "Повторы", 1, 5, 1)],
        }
        for row, key in enumerate(self.state.advanced_order, start=1):
            config = self.state.advanced_options[key]
            enabled_vars[key] = tk.BooleanVar(value=config.get("enabled", False))
            ttk.Checkbutton(window, text=names[key], variable=enabled_vars[key]).grid(
                row=row, column=1, padx=4, pady=2, sticky="w"
            )
            for offset, (parameter, label, minimum, maximum, increment) in enumerate(specs.get(key, [])):
                ttk.Label(window, text=label).grid(row=row, column=2 + offset * 2, padx=(5, 2), sticky="e")
                current = config.get(parameter)
                variable = tk.DoubleVar(value=current) if isinstance(current, float) else tk.IntVar(value=current)
                value_vars[(key, parameter)] = variable
                ttk.Spinbox(
                    window, from_=minimum, to=maximum, increment=increment,
                    textvariable=variable, width=6,
                ).grid(row=row, column=3 + offset * 2, padx=(2, 5), sticky="w")

        def move(direction):
            selection = stages.curselection()
            if not selection:
                return
            old = selection[0]
            new = max(0, min(len(self.state.advanced_order) - 1, old + direction))
            if old == new:
                return
            self.state.advanced_order[old], self.state.advanced_order[new] = (
                self.state.advanced_order[new], self.state.advanced_order[old]
            )
            label = stages.get(old)
            stages.delete(old)
            stages.insert(new, label)
            stages.selection_set(new)

        def save():
            try:
                for key, variable in enabled_vars.items():
                    self.state.advanced_options[key]["enabled"] = variable.get()
                for (key, parameter), variable in value_vars.items():
                    self.state.advanced_options[key][parameter] = variable.get()
                logger.info("Настройки Advance OCR сохранены")
                window.destroy()
            except tk.TclError:
                messagebox.showerror(
                    "Advance OCR", "Проверьте числовые значения параметров.", parent=window
                )

        buttons = ttk.Frame(window)
        buttons.grid(row=10, column=0, columnspan=6, padx=10, pady=10, sticky="ew")
        ttk.Button(buttons, text="Выше", command=lambda: move(-1)).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons, text="Ниже", command=lambda: move(1)).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons, text="Сохранить", command=save).pack(side=tk.RIGHT, padx=3)

    def _update_debug_mode(self):
        """Обновление режима отладки"""
        self.state.debug_mode = self.debug_mode.get()
        logger.info(f"Режим отладки: {self.state.debug_mode}")

        # Обновляем уровень логирования
        import logging
        if self.state.debug_mode:
            logger.logger.setLevel(logging.DEBUG)
            logger.info("Уровень логов переключен на DEBUG")

            # Показываем скрытые колонки
            self.tree.column("expected", width=170, minwidth=50, stretch=tk.YES)
            self.tree.heading("expected", text="Контейнер из XLS")
            self.tree.column("invoice", width=140, minwidth=50, stretch=tk.YES)
            self.tree.heading("invoice", text="Накладная из XLS")
        else:
            logger.logger.setLevel(logging.INFO)
            logger.info("Уровень логов переключен на INFO")

            # Скрываем колонки
            self.tree.column("expected", width=0, minwidth=0, stretch=tk.NO)
            self.tree.heading("expected", text="")
            self.tree.column("invoice", width=0, minwidth=0, stretch=tk.NO)
            self.tree.heading("invoice", text="")

        # Обновляем GUI хендлер
        logger.update_gui_handler(self.text_output)

    def _update_mass_page_scale(self):
        self.state.mass_page_scale = self.mass_page_scale.get()
        mode = "индивидуальный для каждого листа" if self.state.mass_page_scale else "единый (старый режим)"
        logger.info(f"Масштаб массового распознавания: {mode}")

    def _toggle_theme(self):
        """Переключение темы"""
        toggle_theme(self.root)
        self.state.current_theme = "dark" if self.state.current_theme == "light" else "light"

    def _init_ocr_engine(self):
        """Инициализация OCR движка"""
        selected_engine = self.ocr_engine_var.get()
        result = self.app.ocr_service.initialize_engine(selected_engine)

        if result.ok:
            self.state.ocr_engine = result.engine
            logger.info(f"Выбран OCR движок: {result.engine}")
            messagebox.showinfo("Инфо", result.message)
            return

        self.ocr_engine_var.set(self.state.ocr_engine)
        if result.install_hint:
            messagebox.showwarning("OCR движок", f"{result.message}\n\n{result.install_hint}")
        else:
            messagebox.showwarning("OCR движок", result.message)

    def _update_coordinates(self, event=None):
        """Обновление координат из поля ввода"""
        try:
            coordinates_text = self.coordinates_entry.get()
            if coordinates_text:
                coords = coordinates_text.split(",")
                if len(coords) == 4:
                    self.state.x_start, self.state.y_start, self.state.x_end, self.state.y_end = map(int, coords)
                    logger.info(
                        "Координаты обновлены: "
                        f"{self.state.x_start}, {self.state.y_start}, "
                        f"{self.state.x_end}, {self.state.y_end}"
                    )

                    # Обновляем выделение на canvas
                    self.components['canvas'].draw_selection()

                    # Обновляем выбранные области
                    self.state.selected_areas.clear()
                    self.state.selected_areas.append((
                        self.state.rect_id,
                        self.state.x_start,
                        self.state.y_start,
                        self.state.x_end,
                        self.state.y_end
                    ))
        except ValueError as e:
            logger.warning(f"Ошибка формата координат: {e}")

    def on_page_changed(self, page_num):
        """Обработчик изменения текущей страницы"""
        try:
            # Обновляем выделение в таблице
            self._update_table_selection(page_num)

            # Обновляем статус
            self.components['status'].update_status(
                page=page_num + 1,
                total=self.state.total_pages,
                msg=f"Страница {page_num + 1}"
            )

            logger.debug(f"Страница изменена на: {page_num + 1}")

        except Exception as e:
            logger.error(f"Ошибка в обработчике изменения страницы: {e}")

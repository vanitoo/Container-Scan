from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from pdf_ocr_app.gui.main_window_results import MainWindow as ResultsMainWindow
from pdf_ocr_app.utils.logger import logger


class MainWindow(ResultsMainWindow):
    """Experimental UI for selectable form-alignment algorithms."""

    ANALYSIS_METHODS = {
        "Анализ1 — перенос области": "analysis1",
        "Анализ2 — выравнивание листа": "analysis2",
        "Local — уточнить область": "local",
    }

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

        self.analysis_method_var = tk.StringVar(value=next(iter(self.ANALYSIS_METHODS)))
        self.analysis_method_combo = ttk.Combobox(
            frame_left,
            textvariable=self.analysis_method_var,
            values=tuple(self.ANALYSIS_METHODS.keys()),
            state="readonly",
            width=29,
        )
        self.btn_analyze_layout = ttk.Button(
            frame_left,
            text="Анализ",
            command=self._run_selected_analysis,
            width=button_width,
        )

        btn_check = ttk.Button(frame_left, text="Проверить лист", command=self.check_image, width=button_width)
        btn_save_page = ttk.Button(
            frame_left,
            text="Сохранить лист",
            command=self.save_current_page,
            width=button_width,
        )

        btn_prev.pack(side=tk.LEFT, padx=4, pady=2)
        btn_next.pack(side=tk.LEFT, padx=4, pady=2)
        btn_rotate_left.pack(side=tk.LEFT, padx=4, pady=2)
        btn_rotate_right.pack(side=tk.LEFT, padx=4, pady=2)
        self.analysis_method_combo.pack(side=tk.LEFT, padx=(8, 2), pady=2)
        self.btn_analyze_layout.pack(side=tk.LEFT, padx=(2, 4), pady=2)
        btn_check.pack(side=tk.LEFT, padx=4, pady=2)
        btn_save_page.pack(side=tk.LEFT, padx=4, pady=2)

        ttk.Separator(frame_main, orient="vertical").pack(side=tk.LEFT, fill="y", padx=8)
        self.frame_main = frame_main

        frame_right = ttk.Frame(frame_main)
        frame_right.pack(side=tk.RIGHT, fill=tk.X, expand=False)

        self.extra_mode = tk.BooleanVar(value=False)
        options_btn = ttk.Checkbutton(
            frame_right,
            text="Options",
            variable=self.extra_mode,
            command=self.toggle_extra_options,
        )
        options_btn.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            frame_right,
            text="О программе",
            command=lambda: self.updater.show_about(),
        ).pack(side=tk.LEFT, padx=(4, 0))

    def _run_selected_analysis(self):
        """Run the analysis implementation selected in the dropdown."""
        selected_label = self.analysis_method_var.get()
        method = self.ANALYSIS_METHODS.get(selected_label)

        if method == "analysis1":
            logger.info("Запуск Анализ1: шаблон SMGS-01 + перенос области по ORB/Homography")
            self.analyze_layout_v1_template()
            return

        if method == "analysis2":
            logger.info("Запуск Анализ2: выравнивание всего листа по Homography")
            self.analyze_layout_v2()
            return

        if method == "local":
            logger.info("Запуск Local: поиск ячейки рядом с известной областью")
            self.analyze_layout_local()
            return

        messagebox.showwarning(
            "Анализ",
            f"Неизвестный метод анализа: {selected_label}",
        )

    def analyze_layout_v1_template(self):
        """Run Analysis1 against the fixed SMGS-01 template instead of PDF page 1."""
        if not self.state.pdf_doc or self.state.original_page_image is None:
            messagebox.showwarning("Анализ1", "Сначала выберите PDF-файл.")
            return

        try:
            reference_image = self.app.template_service.load_smgs_01()
        except Exception as exc:
            logger.error(f"Анализ1: не удалось загрузить шаблон SMGS-01: {exc}", exc_info=True)
            messagebox.showerror("Анализ1", f"Не удалось загрузить шаблон SMGS-01:\n{exc}")
            return

        if self.state.scale_factor <= 0:
            messagebox.showerror("Анализ1", "Некорректный масштаб текущего листа.")
            return

        # Текущая ручная область хранится в координатах canvas. Переводим её в
        # нормализованные координаты листа и накладываем на постоянный template.png.
        page_width, page_height = self.state.original_page_image.size
        inverse_scale = 1 / self.state.scale_factor
        current_box = (
            round(self.state.x_start * inverse_scale),
            round(self.state.y_start * inverse_scale),
            round(self.state.x_end * inverse_scale),
            round(self.state.y_end * inverse_scale),
        )
        x1, y1, x2, y2 = current_box
        reference_box = (
            round(x1 / page_width * reference_image.width),
            round(y1 / page_height * reference_image.height),
            round(x2 / page_width * reference_image.width),
            round(y2 / page_height * reference_image.height),
        )

        self.btn_analyze_layout.config(state=tk.DISABLED)
        self.components["status"].update_status(msg="Анализ1: сопоставление с шаблоном SMGS-01...")
        page_image = self.state.original_page_image.copy()
        threading.Thread(
            target=self._analyze1_template_worker,
            args=(reference_image, page_image, reference_box),
            daemon=True,
        ).start()

    def _analyze1_template_worker(self, reference_image, page_image, reference_box):
        try:
            result = self.app.pdf_service.align_area_to_reference(
                reference_image,
                page_image,
                reference_box,
            )
            self.root.after(0, self._apply_layout_analysis, result)
        except Exception as exc:
            logger.error(f"Анализ1 по шаблону завершился ошибкой: {exc}", exc_info=True)
            self.root.after(0, self._layout_analysis_failed, str(exc))

    def analyze_layout_local(self):
        """Уточнить область контейнера локально и распознать найденную область."""
        if (
            not self.state.pdf_doc
            or self.state.layout_reference_image is None
            or self.state.layout_reference_box is None
        ):
            messagebox.showwarning(
                "Local",
                "Нет эталона разметки. Загрузите PDF и задайте область на первой странице.",
            )
            return

        self.btn_analyze_layout.config(state=tk.DISABLED)
        self.components["status"].update_status(msg="Local: поиск рамки рядом с областью...")

        page_index = self.state.current_page
        reference_image = self.state.layout_reference_image.copy()
        reference_box = tuple(self.state.layout_reference_box)
        threading.Thread(
            target=self._local_worker,
            args=(page_index, reference_image, reference_box),
            daemon=True,
        ).start()

    def _local_worker(self, page_index, reference_image, reference_box):
        try:
            current_image = self.app.pdf_service.render_page_image(page_index)
            result = self.app.local_analysis_service.analyze(
                reference_image=reference_image,
                current_image=current_image,
                reference_box=reference_box,
            )
            self.root.after(
                0,
                self._apply_local_result,
                page_index,
                current_image,
                result,
            )
        except Exception as exc:
            logger.error(f"Local завершился ошибкой: {exc}", exc_info=True)
            self.root.after(0, self._local_failed, str(exc))

    def _apply_local_result(self, page_index, current_image, result):
        self.btn_analyze_layout.config(state=tk.NORMAL)

        if result.box is None or result.status == "FAILED":
            self.components["status"].update_status(msg="Local FAILED")
            messagebox.showwarning(
                "Local — требуется ручная проверка",
                f"Не удалось уточнить область.\n\n{result.message}",
            )
            return

        self.state.aligned_page_images.pop(page_index, None)
        self.state.original_page_image = current_image.copy()
        if not self.app.pdf_service.create_display_image():
            self._local_failed("Не удалось отобразить исходное изображение")
            return

        x1, y1, x2, y2 = result.box
        scale = self.state.scale_factor
        self.state.x_start = round(x1 * scale)
        self.state.y_start = round(y1 * scale)
        self.state.x_end = round(x2 * scale)
        self.state.y_end = round(y2 * scale)
        self.state.selected_areas = [
            (
                self.state.rect_id,
                self.state.x_start,
                self.state.y_start,
                self.state.x_end,
                self.state.y_end,
            )
        ]
        self.components["canvas"].display_image()

        confidence_text = f"{result.confidence:.0%}"
        logger.info(
            f"Local: status={result.status}, method={result.method}, "
            f"confidence={confidence_text}, box={result.box}"
        )
        self.components["status"].update_status(
            msg=f"Local {result.status}: {result.method}, confidence={confidence_text}"
        )

        self._run_ocr_after_local(page_index, result)

    def _run_ocr_after_local(self, page_index, result):
        try:
            coords = (
                self.state.x_start,
                self.state.y_start,
                self.state.x_end,
                self.state.y_end,
            )
            recognized_text = self.app.ocr_service.recognize_area(page_index, coords)

            if page_index < len(self.state.table_entries):
                self.state.table_entries[page_index]["recognized"] = recognized_text
                item_id = self.state.table_entries[page_index]["item_id"]
                values = list(self.tree.item(item_id, "values"))
                while len(values) < 4:
                    values.append("")
                values[3] = recognized_text
                self.tree.item(item_id, values=values)

            self._show_recognition_result_for_page(page_index)
            confidence_text = f"{result.confidence:.0%}"
            logger.info(
                f"Local: OCR страницы {page_index + 1}: {recognized_text}; "
                f"локализация={result.method}, confidence={confidence_text}"
            )
            self.components["status"].update_status(
                msg=f"Local: OCR={recognized_text}, confidence={confidence_text}"
            )
        except Exception as exc:
            logger.error(f"Local: ошибка OCR: {exc}", exc_info=True)
            messagebox.showerror("Local", f"Область найдена, но OCR завершился ошибкой:\n{exc}")

    def _local_failed(self, error: str):
        self.btn_analyze_layout.config(state=tk.NORMAL)
        self.components["status"].update_status(msg="Local: ошибка")
        messagebox.showerror("Local", f"Не удалось выполнить локальный анализ:\n{error}")

    def analyze_layout_v2(self):
        """Align current scan to the reference page and OCR the reference field."""
        if (
            not self.state.pdf_doc
            or self.state.layout_reference_image is None
            or self.state.layout_reference_box is None
        ):
            messagebox.showwarning(
                "Анализ2",
                "Нет эталона разметки. Загрузите PDF и задайте область на первой странице.",
            )
            return

        self.btn_analyze_layout.config(state=tk.DISABLED)
        self.components["status"].update_status(msg="Анализ2: геометрическая привязка...")

        page_index = self.state.current_page
        reference_image = self.state.layout_reference_image.copy()
        reference_box = tuple(self.state.layout_reference_box)

        threading.Thread(
            target=self._analyze2_worker,
            args=(page_index, reference_image, reference_box),
            daemon=True,
        ).start()

    def _analyze2_worker(self, page_index, reference_image, reference_box):
        try:
            current_image = self.app.pdf_service.render_page_image(page_index)
            result = self.app.alignment_service.align(
                reference_image=reference_image,
                current_image=current_image,
                reference_box=reference_box,
                page_number=page_index + 1,
            )
            self.root.after(
                0,
                self._apply_analyze2_result,
                page_index,
                reference_box,
                result,
            )
        except Exception as exc:
            logger.error(f"Анализ2 завершился ошибкой: {exc}", exc_info=True)
            self.root.after(0, self._analyze2_failed, str(exc))

    def _apply_analyze2_result(self, page_index, reference_box, result):
        self.btn_analyze_layout.config(state=tk.NORMAL)
        self.state.alignment_results[page_index] = result

        error_text = "n/a" if result.reprojection_error is None else f"{result.reprojection_error:.2f}px"
        metrics = (
            f"matches={result.matches}, inliers={result.inliers}, "
            f"ratio={result.inlier_ratio:.0%}, error={error_text}"
        )

        if result.status == "FAILED" or result.aligned_image is None:
            self.components["status"].update_status(msg=f"Анализ2 FAILED: {metrics}")
            messagebox.showwarning(
                "Анализ2 — требуется ручная проверка",
                f"Выравнивание ненадёжно. OCR не запущен.\n\n{metrics}\n\n{result.message}",
            )
            return

        self.app.pdf_service.set_aligned_page(page_index, result.aligned_image)
        self.state.original_page_image = result.aligned_image.copy()
        if not self.app.pdf_service.create_display_image():
            self._analyze2_failed("Не удалось отобразить выровненное изображение")
            return

        scale = self.state.scale_factor
        x1, y1, x2, y2 = reference_box
        self.state.x_start = round(x1 * scale)
        self.state.y_start = round(y1 * scale)
        self.state.x_end = round(x2 * scale)
        self.state.y_end = round(y2 * scale)
        self.state.selected_areas = [
            (
                self.state.rect_id,
                self.state.x_start,
                self.state.y_start,
                self.state.x_end,
                self.state.y_end,
            )
        ]
        self.components["canvas"].display_image()

        if result.status != "GOOD":
            self.components["status"].update_status(msg=f"Анализ2 WARNING: {metrics}")
            messagebox.showwarning(
                "Анализ2 — требуется ручная проверка",
                f"Лист выровнен, но качество привязки пограничное. OCR автоматически не запущен.\n\n{metrics}",
            )
            return

        self.components["status"].update_status(msg=f"Анализ2 GOOD: {metrics}")
        self._run_ocr_after_alignment(page_index)

    def _run_ocr_after_alignment(self, page_index: int):
        try:
            coords = (
                self.state.x_start,
                self.state.y_start,
                self.state.x_end,
                self.state.y_end,
            )
            recognized_text = self.app.ocr_service.recognize_area(page_index, coords)

            if page_index < len(self.state.table_entries):
                self.state.table_entries[page_index]["recognized"] = recognized_text
                item_id = self.state.table_entries[page_index]["item_id"]
                values = list(self.tree.item(item_id, "values"))
                while len(values) < 4:
                    values.append("")
                values[3] = recognized_text
                self.tree.item(item_id, values=values)

            self._show_recognition_result_for_page(page_index)
            logger.info(f"Анализ2: OCR страницы {page_index + 1}: {recognized_text}")
            self.components["status"].update_status(
                msg=f"Анализ2: выравнивание GOOD, OCR={recognized_text}"
            )
        except Exception as exc:
            logger.error(f"Анализ2: ошибка OCR после выравнивания: {exc}", exc_info=True)
            messagebox.showerror("Анализ2", f"Выравнивание выполнено, но OCR завершился ошибкой:\n{exc}")

    def _analyze2_failed(self, error: str):
        self.btn_analyze_layout.config(state=tk.NORMAL)
        self.components["status"].update_status(msg="Анализ2: ошибка")
        messagebox.showerror("Анализ2", f"Не удалось выполнить геометрическую привязку:\n{error}")

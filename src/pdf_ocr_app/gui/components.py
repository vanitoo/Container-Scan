# gui/components.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from pdf_ocr_app.config import CANVAS_SIZE, DOUBLE_CLICK_DELAY
from pdf_ocr_app.utils.logger import logger


class TextRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        self.widget.insert(tk.END, text)
        self.widget.see(tk.END)

    def flush(self):
        pass


class CanvasComponent:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.state = app.state
        self.canvas = None
        self.canvas2 = None
        self.recognition_text = None
        self.preview_filters_var = None

    def display_image(self):
        """Отображение текущего изображения на canvas"""
        if self.state.image_display and self.canvas:
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.state.image_display)
            self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

            if (self.state.x_start and self.state.y_start and
                    self.state.x_end and self.state.y_end):
                self.draw_selection()

            self._update_zoom_status()
            logger.debug("Изображение отображено на canvas")

    def create_canvases(self):
        canvas_width, canvas_height = CANVAS_SIZE

        page_frame = ttk.Frame(self.parent)
        page_frame.pack(side=tk.LEFT, anchor=tk.N, padx=6, pady=10)
        self.canvas = tk.Canvas(
            page_frame,
            width=canvas_width,
            height=canvas_height,
            bg="#F3F4F6",
            highlightthickness=0,
        )
        page_scroll_y = ttk.Scrollbar(page_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        page_scroll_x = ttk.Scrollbar(page_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(
            yscrollcommand=page_scroll_y.set,
            xscrollcommand=page_scroll_x.set,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        page_scroll_y.grid(row=0, column=1, sticky="ns")
        page_scroll_x.grid(row=1, column=0, sticky="ew")
        page_frame.grid_rowconfigure(0, weight=1)
        page_frame.grid_columnconfigure(0, weight=1)

        preview_frame = ttk.Frame(self.parent)
        preview_frame.pack(side=tk.LEFT, anchor=tk.N, padx=6, pady=10)

        preview_toolbar = ttk.Frame(preview_frame)
        preview_toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        self.preview_filters_var = tk.BooleanVar(value=self.state.preview_ocr_filters)
        ttk.Checkbutton(
            preview_toolbar,
            text="Предпросмотр OCR-фильтров",
            variable=self.preview_filters_var,
            command=self._toggle_filter_preview,
        ).pack(side=tk.LEFT)

        self.canvas2 = tk.Canvas(
            preview_frame,
            width=canvas_width,
            height=int(canvas_height * 0.62),
            bg="#F3F4F6",
            highlightthickness=0
        )
        self.canvas2.pack(side=tk.TOP, anchor=tk.N)

        ttk.Label(preview_frame, text="Результат распознавания").pack(
            side=tk.TOP, anchor=tk.W, pady=(8, 3)
        )
        self.recognition_text = tk.Text(
            preview_frame,
            width=46,
            height=8,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg="#F8FAFC",
            relief=tk.SOLID,
            borderwidth=1,
        )
        self.recognition_text.pack(side=tk.TOP, fill=tk.X)

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_canvas_zoom)
        self.canvas.bind("<ButtonPress-3>", self.on_canvas_pan_start)
        self.canvas.bind("<B3-Motion>", self.on_canvas_pan_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_canvas_pan_end)
        self.canvas2.bind("<MouseWheel>", self.on_canvas2_zoom)

    def _toggle_filter_preview(self):
        self.state.preview_ocr_filters = bool(self.preview_filters_var.get())
        mode = "включён" if self.state.preview_ocr_filters else "выключен"
        logger.info(f"Предпросмотр OCR-фильтров: {mode}")
        self.update_cropped_image()

    def refresh_filter_preview(self):
        """Перерисовать preview после изменения OCR-настроек."""
        if self.state.preview_ocr_filters:
            self.update_cropped_image()

    def on_canvas_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.config(cursor="fleur")

    def on_canvas_pan_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_canvas_pan_end(self, _event):
        self.canvas.config(cursor="")

    def show_recognition_result(self, result: dict | None):
        """Show OCR details below the cropped-image preview."""
        if self.recognition_text is None:
            return

        if result:
            text = (
                f"Страница: {result.get('page', '')}\n"
                f"Движок: {result.get('engine', '')}\n\n"
                "Исходный текст:\n"
                f"{result.get('raw_text', '')}\n\n"
                "Форматированный текст:\n"
                f"{result.get('formatted_text', '')}"
            )
        else:
            text = ""

        self.recognition_text.config(state=tk.NORMAL)
        self.recognition_text.delete("1.0", tk.END)
        self.recognition_text.insert("1.0", text)
        self.recognition_text.config(state=tk.DISABLED)

    def on_canvas_click(self, event):
        self.state.x_start = round(self.canvas.canvasx(event.x))
        self.state.y_start = round(self.canvas.canvasy(event.y))

        if self.state.rect_id:
            self.canvas.delete(self.state.rect_id)

        self.state.rect_id = self.canvas.create_rectangle(
            self.state.x_start, self.state.y_start,
            self.state.x_start, self.state.y_start,
            outline="red", width=2
        )
        self.update_coordinates_display()

    def on_canvas_drag(self, event):
        x_end = round(self.canvas.canvasx(event.x))
        y_end = round(self.canvas.canvasy(event.y))
        if self.state.rect_id is not None:
            self.canvas.coords(
                self.state.rect_id,
                self.state.x_start, self.state.y_start,
                x_end, y_end
            )

    def on_canvas_release(self, event):
        self.state.x_end = round(self.canvas.canvasx(event.x))
        self.state.y_end = round(self.canvas.canvasy(event.y))

        if self.state.x_end < self.state.x_start:
            self.state.x_start, self.state.x_end = self.state.x_end, self.state.x_start
        if self.state.y_end < self.state.y_start:
            self.state.y_start, self.state.y_end = self.state.y_end, self.state.y_start

        self.canvas.coords(
            self.state.rect_id,
            self.state.x_start, self.state.y_start,
            self.state.x_end, self.state.y_end
        )

        self.state.selected_areas.clear()
        self.state.selected_areas.append((
            self.state.rect_id,
            self.state.x_start,
            self.state.y_start,
            self.state.x_end,
            self.state.y_end
        ))

        self.update_coordinates_display()
        self.update_cropped_image()

    def on_canvas_release_new(self, event):
        self.state.x_end, self.state.y_end = event.x, event.y
        if self.state.x_end < self.state.x_start:
            self.state.x_start, self.state.x_end = self.state.x_end, self.state.x_start
        if self.state.y_end < self.state.y_start:
            self.state.y_start, self.state.y_end = self.state.y_end, self.state.y_start

        if self.state.rect_id is not None:
            self.canvas.coords(
                self.state.rect_id,
                self.state.x_start, self.state.y_start,
                self.state.x_end, self.state.y_end
            )
        else:
            self.state.rect_id = self.canvas.create_rectangle(
                self.state.x_start, self.state.y_start,
                self.state.x_end, self.state.y_end,
                outline="red", width=2
            )

        self.state.selected_areas.clear()
        self.state.selected_areas.append((
            self.state.rect_id,
            self.state.x_start,
            self.state.y_start,
            self.state.x_end,
            self.state.y_end
        ))

        try:
            page_img = getattr(self.state, "page_image", None)
            w = page_img.width if page_img is not None else None
            h = page_img.height if page_img is not None else None
            if w and h:
                x1n = max(0.0, min(1.0, self.state.x_start / w))
                y1n = max(0.0, min(1.0, self.state.y_start / h))
                x2n = max(0.0, min(1.0, self.state.x_end / w))
                y2n = max(0.0, min(1.0, self.state.y_end / h))
                self.state.selection_rect_norm = (x1n, y1n, x2n, y2n)
        except Exception:
            pass

        self.update_coordinates_display()
        self.update_cropped_image()

    def on_canvas_zoom(self, event):
        if not self.state.original_page_image:
            return

        mouse_x = self.canvas.canvasx(event.x)
        mouse_y = self.canvas.canvasy(event.y)
        zoom_factor = 1.1 if event.delta > 0 else 0.9
        new_scale = self.state.canvas_scale * zoom_factor
        new_scale = max(0.1, min(new_scale, 5.0))

        if new_scale == self.state.canvas_scale:
            return

        previous_scale = self.state.canvas_scale
        coordinate_ratio = new_scale / previous_scale
        self.state.canvas_scale = new_scale
        self.state.scale_factor = new_scale
        self.state.last_scale_factor = new_scale
        new_width = int(self.state.original_page_image.width * self.state.canvas_scale)
        new_height = int(self.state.original_page_image.height * self.state.canvas_scale)
        scaled_image = self.state.original_page_image.resize((new_width, new_height), Image.LANCZOS)
        self.state.page_image = scaled_image

        self.state.x_start = round(self.state.x_start * coordinate_ratio)
        self.state.y_start = round(self.state.y_start * coordinate_ratio)
        self.state.x_end = round(self.state.x_end * coordinate_ratio)
        self.state.y_end = round(self.state.y_end * coordinate_ratio)
        self.state.selected_areas = [
            (
                self.state.rect_id,
                self.state.x_start,
                self.state.y_start,
                self.state.x_end,
                self.state.y_end,
            )
        ]

        self.canvas.delete("all")
        img_tk = ImageTk.PhotoImage(scaled_image)
        self.canvas.image = img_tk
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        self.state.rect_id = self.canvas.create_rectangle(
            self.state.x_start,
            self.state.y_start,
            self.state.x_end,
            self.state.y_end,
            outline="red",
            width=2,
        )
        self.canvas.config(scrollregion=(0, 0, new_width, new_height))

        self.canvas.xview_moveto((mouse_x * coordinate_ratio - event.x) / new_width)
        self.canvas.yview_moveto((mouse_y * coordinate_ratio - event.y) / new_height)
        self.update_coordinates_display()
        self.update_cropped_image()
        self._update_zoom_status()

    def on_canvas2_zoom(self, event):
        if not self.state.cropped_image:
            return

        mouse_x = self.canvas2.canvasx(event.x)
        mouse_y = self.canvas2.canvasy(event.y)
        zoom_factor = 1.1 if event.delta > 0 else 0.9
        new_scale = self.state.canvas2_scale * zoom_factor
        new_scale = max(0.5, min(new_scale, 5.0))
        if new_scale == self.state.canvas2_scale:
            return

        self.state.canvas2_scale = new_scale
        new_width = int(self.state.cropped_image.width * self.state.canvas2_scale)
        new_height = int(self.state.cropped_image.height * self.state.canvas2_scale)
        scaled_img = self.state.cropped_image.resize((new_width, new_height), Image.LANCZOS)

        self.canvas2.delete("all")
        self.canvas2.image = ImageTk.PhotoImage(scaled_img)
        self.canvas2.create_image(0, 0, anchor=tk.NW, image=self.canvas2.image)
        self.canvas2.config(scrollregion=(0, 0, new_width, new_height))
        self.canvas2.xview_moveto((mouse_x * zoom_factor - event.x) / new_width)
        self.canvas2.yview_moveto((mouse_y * zoom_factor - event.y) / new_height)

        try:
            self._update_zoom_status()
        except Exception as e:
            logger.debug(f"Ошибка обновления статуса масштаба: {e}")

    def _update_zoom_status(self):
        try:
            self.app.gui.components["status"].update_status(
                page_zoom=f"{round(self.state.canvas_scale * 100)}%",
                area_zoom=f"{round(self.state.canvas2_scale * 100)}%",
            )
        except Exception as e:
            logger.debug(f"Ошибка обновления масштабов: {e}")

    def update_coordinates_display(self):
        if hasattr(self.app.gui, 'coordinates_entry'):
            coordinates_text = f"{self.state.x_start},{self.state.y_start},{self.state.x_end},{self.state.y_end}"
            self.app.gui.coordinates_entry.delete(0, tk.END)
            self.app.gui.coordinates_entry.insert(0, coordinates_text)

    def update_cropped_image(self):
        """Обновление выделенной области и, при необходимости, OCR-preview."""
        if not self.state.page_image:
            logger.warning("Нет page_image для обновления обрезанного изображения")
            return

        try:
            inverse_scale = 1 / self.state.scale_factor
            x1 = int(self.state.x_start * inverse_scale)
            y1 = int(self.state.y_start * inverse_scale)
            x2 = int(self.state.x_end * inverse_scale)
            y2 = int(self.state.y_end * inverse_scale)

            if x2 <= x1 or y2 <= y1:
                logger.error("Некорректные координаты выделенной области")
                return

            if self.state.original_page_image:
                original_width, original_height = self.state.original_page_image.size
                x1 = max(0, min(x1, original_width - 1))
                y1 = max(0, min(y1, original_height - 1))
                x2 = max(1, min(x2, original_width))
                y2 = max(1, min(y2, original_height))
                if x2 <= x1 or y2 <= y1:
                    return
                raw_cropped = self.state.original_page_image.crop((x1, y1, x2, y2))
            else:
                page_width, page_height = self.state.page_image.size
                x1_scaled = max(0, min(self.state.x_start, page_width - 1))
                y1_scaled = max(0, min(self.state.y_start, page_height - 1))
                x2_scaled = max(1, min(self.state.x_end, page_width))
                y2_scaled = max(1, min(self.state.y_end, page_height))
                raw_cropped = self.state.page_image.crop((x1_scaled, y1_scaled, x2_scaled, y2_scaled))

            self.state.cropped_image = raw_cropped
            display_cropped = raw_cropped

            if self.state.preview_ocr_filters:
                try:
                    coords = (
                        self.state.x_start,
                        self.state.y_start,
                        self.state.x_end,
                        self.state.y_end,
                    )
                    prepared = self.app.ocr_service.prepare_preview_image(
                        self.state.current_page,
                        coords,
                    )
                    if prepared is not None:
                        display_cropped = prepared
                        logger.debug(
                            "Canvas2 показывает OCR-preview: режим=%s, размер=%s",
                            "Advance" if self.state.recognition_mode == 1 else (
                                "Legacy 2.0.3" if self.state.use_legacy_tesseract else "Текущий"
                            ),
                            prepared.size,
                        )
                except Exception as exc:
                    logger.warning(f"Не удалось построить OCR-preview: {exc}")

            # Для zoom на canvas2 храним именно отображаемую картинку.
            self.state.cropped_image = display_cropped
            cropped_width, cropped_height = display_cropped.size
            if cropped_width == 0 or cropped_height == 0:
                return

            self.state.canvas2_scale = 1.0
            scaled_img = display_cropped.resize((cropped_width, cropped_height), Image.LANCZOS)

            self.canvas2.delete("all")
            self.canvas2.image = ImageTk.PhotoImage(scaled_img)
            self.canvas2.create_image(0, 0, anchor=tk.NW, image=self.canvas2.image)
            self.canvas2.config(scrollregion=self.canvas2.bbox(tk.ALL))
            self._update_zoom_status()

        except Exception as e:
            logger.error(f"ОШИБКА в update_cropped_image: {e}")

    def draw_selection(self):
        if self.state.rect_id:
            self.canvas.delete(self.state.rect_id)

        self.state.rect_id = self.canvas.create_rectangle(
            self.state.x_start, self.state.y_start,
            self.state.x_end, self.state.y_end,
            outline="red", width=2
        )
        self.update_coordinates_display()
        self.update_cropped_image()


class TableComponent:
    ROW_COLORS = {
        "exact_match": ("#a8e6a8", "#d3f5d3"),
        "partial_match": ("#fff8a8", "#fffcd9"),
        "no_match": ("#ffaaaa", "#ffd8d8"),
        "manual_edit": ("#ddaaff", "#efd9ff"),
    }
    SELECTED_NEUTRAL = "#DFECFF"

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.state = app.state
        self.tree = None
        self.last_click_time = 0
        self._prevent_selection_loop = False
        self._edit_tooltip = None
        self._edit_tooltip_after = None
        self._hovered_edit_cell = None

    def create_table(self):
        table_frame = ttk.Frame(self.parent)
        table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(table_frame, yscrollcommand=tree_scroll.set, selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)

        self.tree["columns"] = (
            "number", "expected", "invoice", "recognized", "match", "score", "differences"
        )
        self.tree.column("#0", width=0, stretch=tk.NO)
        self.tree.column("number", width=60, anchor=tk.CENTER)
        self.tree.column("expected", width=0, minwidth=0, stretch=tk.NO)
        self.tree.column("invoice", width=0, stretch=tk.NO)
        self.tree.column("recognized", width=170, anchor=tk.W)
        self.tree.column("match", width=170, anchor=tk.W)
        self.tree.column("score", width=80, anchor=tk.CENTER)
        self.tree.column("differences", width=210, anchor=tk.W)

        self.tree.heading("number", text="№")
        self.tree.heading("expected", text="Контейнер из XLS")
        self.tree.heading("invoice", text="Накладная (XLS)")
        self.tree.heading("recognized", text="Контейнер распознанный")
        self.tree.heading("match", text="Совпадение")
        self.tree.heading("score", text="Коэффициент")
        self.tree.heading("differences", text="Различия: распознано → совпадение")

        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Return>", self.on_tree_enter)
        self.tree.bind("<Motion>", self.on_tree_motion)
        self.tree.bind("<Leave>", self.hide_edit_tooltip)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_selection_changed)

        for base, (_normal, selected_color) in self.ROW_COLORS.items():
            self.tree.tag_configure(
                f"{base}_selected",
                background=selected_color,
                foreground="#111827",
            )
        self.tree.tag_configure(
            "_neutral_selected",
            background=self.SELECTED_NEUTRAL,
            foreground="#111827",
        )

        return self.tree

    @staticmethod
    def format_differences(recognized: str, matched: str) -> str:
        recognized = (recognized or "").strip().upper()
        matched = (matched or "").strip().upper()
        if not recognized or not matched:
            return "—"

        differences = []
        max_length = max(len(recognized), len(matched))
        for index in range(max_length):
            actual = recognized[index] if index < len(recognized) else "∅"
            expected = matched[index] if index < len(matched) else "∅"
            if actual != expected:
                differences.append(f"{index + 1}: {actual}→{expected}")
        return "; ".join(differences) if differences else "Совпадает полностью"

    def update_match_summary(self):
        if self.tree is None:
            return

        rows = self.tree.get_children()
        total = len(rows)
        matched = 0
        for item in rows:
            tags = set(self.tree.item(item, "tags"))
            values = self.tree.item(item, "values")
            has_match = len(values) > 4 and bool(str(values[4]).strip())
            if has_match and ("exact_match" in tags or "manual_edit" in tags):
                matched += 1
        remaining = total - matched
        status = self.app.gui.components.get("status")
        if status is not None:
            status.update_status(
                match_summary=f"Всего: {total} | Сопоставлено: {matched} | Осталось: {remaining}"
            )

    def _on_tree_selection_changed(self, _event=None):
        self.refresh_selection_highlight()

    def refresh_selection_highlight(self):
        if self.tree is None:
            return

        for item in self.tree.get_children():
            tags = list(self.tree.item(item, "tags"))
            filtered = [t for t in tags if not t.endswith("_selected")]
            if len(filtered) != len(tags):
                self.tree.item(item, tags=tuple(filtered))

        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        tags = list(self.tree.item(item, "tags"))
        selected_tag = next(
            (f"{base}_selected" for base in self.ROW_COLORS if base in tags),
            "_neutral_selected",
        )
        tags.append(selected_tag)
        self.tree.item(item, tags=tuple(tags))

    def on_tree_click(self, event):
        self.hide_edit_tooltip()
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        current_time = event.time
        is_double_click = (current_time - self.last_click_time) < DOUBLE_CLICK_DELAY
        self.last_click_time = current_time

        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)

        self.goto_page(item)

        if is_double_click:
            if column == "#5":
                self.edit_cell(item, column)
            elif column == "#4":
                self.copy_recognized_to_clipboard(item, event)

    def on_tree_motion(self, event):
        region = self.tree.identify_region(event.x, event.y)
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        hovered_cell = (item, column) if region == "cell" and item and column == "#5" else None

        if hovered_cell == self._hovered_edit_cell:
            return

        self.hide_edit_tooltip()
        self._hovered_edit_cell = hovered_cell
        if hovered_cell is None:
            self.tree.config(cursor="")
            return

        self.tree.config(cursor="hand2")
        x_root = event.x_root + 12
        y_root = event.y_root + 14
        self._edit_tooltip_after = self.tree.after(
            350,
            lambda: self.show_edit_tooltip(x_root, y_root),
        )

    def show_edit_tooltip(self, x_root: int, y_root: int):
        self._edit_tooltip_after = None
        if self._hovered_edit_cell is None:
            return

        self._edit_tooltip = tk.Toplevel(self.app.root)
        self._edit_tooltip.wm_overrideredirect(True)
        self._edit_tooltip.wm_geometry(f"+{x_root}+{y_root}")
        tk.Label(
            self._edit_tooltip,
            text="Двойной щелчок — редактировать совпадение",
            background="#FFF7CC",
            foreground="#111827",
            font=("Arial", 9),
            padx=8,
            pady=5,
            relief="solid",
            borderwidth=1,
        ).pack()

    def hide_edit_tooltip(self, _event=None):
        if self._edit_tooltip_after is not None:
            self.tree.after_cancel(self._edit_tooltip_after)
            self._edit_tooltip_after = None
        if self._edit_tooltip is not None:
            self._edit_tooltip.destroy()
            self._edit_tooltip = None
        self._hovered_edit_cell = None
        if self.tree is not None:
            self.tree.config(cursor="")

    def on_tree_enter(self, event):
        item = self.tree.focus() or (self.tree.selection()[0] if self.tree.selection() else None)
        if not item:
            children = self.tree.get_children()
            if not children:
                return "break"
            item = children[0]
            self.tree.selection_set(item)
            self.tree.focus(item)

        self.tree.see(item)
        self.goto_page(item)
        self.edit_cell(item, "#5")
        return "break"

    def on_tree_selection_change(self, event):
        return

    def goto_page(self, item):
        values = self.tree.item(item, "values")
        if values and values[0]:
            try:
                page_num = int(values[0]) - 1
                self.app.gui.goto_page_from_table(page_num)
            except ValueError:
                pass

    def copy_recognized_to_clipboard(self, item, event):
        values = self.tree.item(item, "values")
        if len(values) > 3 and values[3]:
            recognized_text = values[3]
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(recognized_text)
            self.show_copy_tooltip(event, recognized_text)

    def show_copy_tooltip(self, event, text):
        tooltip = tk.Toplevel(self.app.root)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

        label = tk.Label(
            tooltip,
            text=f"Скопировано: {text}",
            background="lightgreen",
            foreground="black",
            font=("Arial", 9),
            padx=8,
            pady=4,
            relief="solid",
            borderwidth=1
        )
        label.pack()
        tooltip.after(1500, tooltip.destroy)

    def edit_cell(self, item, column):
        expected_containers = []
        for _xls_id, container in self.state.all_excel_records:
            if container and container not in expected_containers:
                expected_containers.append(container)

        expected_containers.sort()
        x, y, width, height = self.tree.bbox(item, column)
        current_value = self.tree.item(item, "values")[4]

        first_input = {"done": False}
        entry_edit = tk.Entry(self.tree, borderwidth=0, font=("Arial", 10))
        entry_edit.place(x=x, y=y, width=width, height=height, anchor=tk.NW)
        entry_edit.insert(0, current_value)
        entry_edit.focus_set()

        listbox = tk.Listbox(self.tree, height=min(15, len(expected_containers)))
        listbox.place(x=x, y=y + height, width=width)

        def update_listbox():
            typed = entry_edit.get()
            matches = [c for c in expected_containers if typed.upper() in c.upper()]
            listbox.delete(0, tk.END)
            for match in matches:
                listbox.insert(tk.END, match)
            if matches:
                listbox.place(x=x, y=y + height, width=width, height=min(200, len(matches) * 20))
            else:
                listbox.place_forget()

        def on_key_release(event):
            if not first_input["done"]:
                if event.keysym in ("BackSpace", "Delete"):
                    first_input["done"] = True
                    update_listbox()
                    return

                if event.char and len(event.char) == 1 and event.char.isprintable():
                    char = event.char.upper()
                    entry_edit.delete(0, tk.END)
                    entry_edit.insert(0, char)
                    entry_edit.icursor(1)
                    first_input["done"] = True
                    update_listbox()
                return

            if event.keysym in ("Up", "Down", "Return"):
                return

            pos = entry_edit.index(tk.INSERT)
            text = entry_edit.get().upper()
            entry_edit.delete(0, tk.END)
            entry_edit.insert(0, text)
            entry_edit.icursor(pos)
            update_listbox()

        def go_to_next_row():
            rows = list(self.tree.get_children())
            try:
                index = rows.index(item)
            except ValueError:
                return

            next_item = None
            for candidate in rows[index + 1:]:
                tags = set(self.tree.item(candidate, "tags"))
                values = self.tree.item(candidate, "values")
                has_match = len(values) > 4 and bool(str(values[4]).strip())
                is_completed = has_match and (
                    "exact_match" in tags or "manual_edit" in tags
                )
                if not is_completed:
                    next_item = candidate
                    break

            if next_item is None:
                self.tree.focus_set()
                return
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)
            self.goto_page(next_item)
            self.tree.after(10, lambda: self.edit_cell(next_item, "#5"))

        def on_entry_key(event):
            if event.keysym == "Down" and listbox.size() > 0:
                listbox.focus_set()
                listbox.selection_clear(0, tk.END)
                listbox.selection_set(0)
                listbox.activate(0)
                return "break"

            if event.keysym == "Return":
                if listbox.winfo_ismapped() and listbox.size() == 1:
                    selected = listbox.get(0)
                    entry_edit.delete(0, tk.END)
                    entry_edit.insert(0, selected)
                    listbox.place_forget()
                    entry_edit.focus_set()
                save_edit()
                go_to_next_row()
                return "break"

            if event.keysym == "Escape":
                listbox.place_forget()
                entry_edit.destroy()
                self.tree.focus_set()
                return "break"

            return None

        def on_listbox_key(event):
            if event.keysym == "Return":
                on_listbox_select(None)
                save_edit()
                go_to_next_row()
                return "break"
            elif event.keysym == "Escape":
                listbox.place_forget()
                entry_edit.focus_set()
                return "break"

        def on_listbox_select(event):
            if listbox.curselection():
                selected = listbox.get(listbox.curselection())
                entry_edit.delete(0, tk.END)
                entry_edit.insert(0, selected)
                listbox.place_forget()
                entry_edit.focus_set()

        def save_edit(event=None):
            new_value = entry_edit.get()
            values = list(self.tree.item(item, "values"))
            values[4] = new_value
            while len(values) < 7:
                values.append("")
            values[6] = self.format_differences(values[3], new_value)

            self.tree.tag_configure("manual_edit", background="#ddaaff")
            self.tree.item(item, tags=("manual_edit",))
            self.refresh_selection_highlight()

            self.tree.item(item, values=values)
            self.update_match_summary()
            entry_edit.destroy()
            listbox.place_forget()

        def on_entry_focus_out(event):
            widget = event.widget.focus_get()
            if widget != listbox:
                save_edit()

        entry_edit.bind("<KeyRelease>", on_key_release)
        entry_edit.bind("<FocusOut>", on_entry_focus_out)
        entry_edit.bind("<KeyPress>", on_entry_key)
        listbox.bind("<<ListboxSelect>>", on_listbox_select)
        listbox.bind("<Return>", on_listbox_key)
        listbox.bind("<Escape>", on_listbox_key)
        listbox.bind("<Double-Button-1>", on_listbox_select)
        listbox.bind("<FocusOut>", lambda e: listbox.place_forget())
        update_listbox()

    def bind_navigation_keys(self):
        self.tree.bind("<Up>", self.on_arrow_key)
        self.tree.bind("<Down>", self.on_arrow_key)
        self.tree.bind("<Home>", self.on_arrow_key)
        self.tree.bind("<End>", self.on_arrow_key)
        self.tree.bind("<Prior>", self.on_arrow_key)
        self.tree.bind("<Next>", self.on_arrow_key)

    def on_arrow_key(self, event):
        def update_after_navigation():
            current_selection = self.tree.selection()
            if current_selection:
                self.goto_page(current_selection[0])

        self.tree.after(10, update_after_navigation)


class StatusBar:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.state = app.state

        self.status_page_var = tk.StringVar(value="Стр: —/—")
        self.status_page_zoom_var = tk.StringVar(value="Лист: 100%")
        self.status_area_zoom_var = tk.StringVar(value="Область: 100%")
        self.status_size_var = tk.StringVar(value="Размер листа: —×—")
        self.status_match_var = tk.StringVar(value="Всего: 0 | Сопоставлено: 0 | Осталось: 0")
        self.status_msg_var = tk.StringVar(value="Готово")

    def create_statusbar(self):
        statusbar = ttk.Frame(self.parent, style="Toolbar.TFrame")
        statusbar.pack(side=tk.BOTTOM, fill="x")

        ttk.Label(statusbar, textvariable=self.status_page_var).pack(side=tk.LEFT, padx=8, pady=4)
        ttk.Label(statusbar, text="|").pack(side=tk.LEFT, padx=6)
        ttk.Label(statusbar, textvariable=self.status_page_zoom_var).pack(side=tk.LEFT, padx=8)
        ttk.Label(statusbar, text="|").pack(side=tk.LEFT, padx=6)
        ttk.Label(statusbar, textvariable=self.status_area_zoom_var).pack(side=tk.LEFT, padx=8)
        ttk.Label(statusbar, text="|").pack(side=tk.LEFT, padx=6)
        ttk.Label(statusbar, textvariable=self.status_size_var).pack(side=tk.LEFT, padx=8)
        ttk.Label(statusbar, text="|").pack(side=tk.LEFT, padx=6)
        ttk.Label(statusbar, textvariable=self.status_match_var).pack(side=tk.LEFT, padx=8)
        ttk.Label(statusbar, textvariable=self.status_msg_var).pack(side=tk.RIGHT, padx=8)

    def update_status(
        self, page=None, total=None, zoom=None, page_zoom=None, area_zoom=None,
        size=None, match_summary=None, msg=None
    ):
        if page is not None and total is not None:
            self.status_page_var.set(f"Стр: {page}/{total}")
            size = self._current_page_size()
        if zoom is not None:
            area_zoom = zoom
        if page_zoom is not None:
            self.status_page_zoom_var.set(f"Лист: {page_zoom}")
        if area_zoom is not None:
            self.status_area_zoom_var.set(f"Область: {area_zoom}")
        if size is not None:
            self.status_size_var.set(f"Размер листа: {size}")
        if match_summary is not None:
            self.status_match_var.set(match_summary)
        if msg is not None:
            self.status_msg_var.set(msg)

    def _current_page_size(self) -> str | None:
        document = self.state.pdf_doc
        if document is None or document.page_count == 0:
            return None

        try:
            page_index = max(0, min(self.state.current_page, document.page_count - 1))
            rect = document.load_page(page_index).rect
            width_mm = rect.width * 25.4 / 72
            height_mm = rect.height * 25.4 / 72
            dimensions = (
                f"{rect.width:.1f}×{rect.height:.1f} pt "
                f"({width_mm:.1f}×{height_mm:.1f} мм)"
            )

            image = self.state.original_page_image
            if image is not None:
                dimensions += f", {image.width}×{image.height} px"
            return dimensions
        except Exception as exc:
            logger.debug(f"Не удалось получить размер текущего листа: {exc}")
            return None

# gui/components.py
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, scrolledtext
import webbrowser
from PIL import Image, ImageTk

from config import CANVAS_SIZE, DOUBLE_CLICK_DELAY
from utils.logger import logger


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

    # gui/components.py (добавляем в класс CanvasComponent)
    def display_image(self):
        """Отображение текущего изображения на canvas"""
        if self.state.image_display and self.canvas:
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.state.image_display)
            self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

            # Перерисовываем выделение если есть
            if (self.state.x_start and self.state.y_start and
                    self.state.x_end and self.state.y_end):
                self.draw_selection()

            logger.debug("Изображение отображено на canvas")

    def create_canvases(self):
        canvas_width, canvas_height = CANVAS_SIZE
        self.canvas = tk.Canvas(
            self.parent,
            width=canvas_width,
            height=canvas_height,
            bg="#F3F4F6",
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, anchor=tk.N, padx=6, pady=10)

        self.canvas2 = tk.Canvas(
            self.parent,
            width=canvas_width,
            height=canvas_height,
            bg="#F3F4F6",
            highlightthickness=0
        )
        self.canvas2.pack(side=tk.LEFT, anchor=tk.N, padx=6, pady=10)

        # Бинды событий
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_canvas_zoom)
        self.canvas2.bind("<MouseWheel>", self.on_canvas2_zoom)

    def on_canvas_click(self, event):
        self.state.x_start = event.x
        self.state.y_start = event.y

        if self.state.rect_id:
            self.canvas.delete(self.state.rect_id)

        self.state.rect_id = self.canvas.create_rectangle(
            self.state.x_start, self.state.y_start,
            self.state.x_start, self.state.y_start,
            outline="red", width=2
        )
        self.update_coordinates_display()

    def on_canvas_drag(self, event):
        x_end, y_end = event.x, event.y
        if self.state.rect_id is not None:
            self.canvas.coords(
                self.state.rect_id,
                self.state.x_start, self.state.y_start,
                x_end, y_end
            )

    def on_canvas_release(self, event):
        self.state.x_end, self.state.y_end = event.x, event.y

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
        """Фиксируем финальные координаты выделения, нормализуем и сохраняем их в состоянии."""
        # Конечные координаты курсора
        self.state.x_end, self.state.y_end = event.x, event.y

        # Нормализация порядка координат (x1 <= x2, y1 <= y2)
        if self.state.x_end < self.state.x_start:
            self.state.x_start, self.state.x_end = self.state.x_end, self.state.x_start
        if self.state.y_end < self.state.y_start:
            self.state.y_start, self.state.y_end = self.state.y_end, self.state.y_start

        # Обновляем прямоугольник на Canvas
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

        # Обновляем список выделений (храним актуальное)
        self.state.selected_areas.clear()
        self.state.selected_areas.append((
            self.state.rect_id,
            self.state.x_start,
            self.state.y_start,
            self.state.x_end,
            self.state.y_end
        ))

        # Сохраняем нормализованное выделение (в долях от размеров отображаемого изображения)
        try:
            page_img = getattr(self.state, "page_image", None)
            w = page_img.width if page_img is not None else None
            h = page_img.height if page_img is not None else None
            if w and h:
                x1n = self.state.x_start / w
                y1n = self.state.y_start / h
                x2n = self.state.x_end / w
                y2n = self.state.y_end / h
                # Клип к [0..1]
                x1n = max(0.0, min(1.0, x1n))
                y1n = max(0.0, min(1.0, y1n))
                x2n = max(0.0, min(1.0, x2n))
                y2n = max(0.0, min(1.0, y2n))
                self.state.selection_rect_norm = (x1n, y1n, x2n, y2n)
        except Exception:
            # Не критично — просто не сохраняем нормализованную форму
            pass

        # Обновляем подписи/второй холст
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

        self.state.canvas_scale = new_scale
        new_width = int(self.state.original_page_image.width * self.state.canvas_scale)
        new_height = int(self.state.original_page_image.height * self.state.canvas_scale)
        scaled_image = self.state.original_page_image.resize((new_width, new_height), Image.LANCZOS)

        self.canvas.delete("all")
        img_tk = ImageTk.PhotoImage(scaled_image)
        self.canvas.image = img_tk
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        self.canvas.config(scrollregion=(0, 0, new_width, new_height))

        self.canvas.xview_moveto((mouse_x * zoom_factor - event.x) / new_width)
        self.canvas.yview_moveto((mouse_y * zoom_factor - event.y) / new_height)

    def on_canvas2_zoom(self, event):
        """Масштабирование на втором холсте"""
        if not self.state.cropped_image:
            return

        # Получаем координаты мыши относительно canvas2
        mouse_x = self.canvas2.canvasx(event.x)
        mouse_y = self.canvas2.canvasy(event.y)

        # Устанавливаем коэффициент масштабирования
        zoom_factor = 1.1 if event.delta > 0 else 0.9
        new_scale = self.state.canvas2_scale * zoom_factor

        # Ограничения масштаба
        new_scale = max(0.5, min(new_scale, 5.0))
        if new_scale == self.state.canvas2_scale:
            return

        self.state.canvas2_scale = new_scale

        # Новые размеры изображения
        new_width = int(self.state.cropped_image.width * self.state.canvas2_scale)
        new_height = int(self.state.cropped_image.height * self.state.canvas2_scale)

        # Масштабируем изображение
        scaled_img = self.state.cropped_image.resize((new_width, new_height), Image.LANCZOS)

        # Обновляем canvas2
        self.canvas2.delete("all")
        self.canvas2.image = ImageTk.PhotoImage(scaled_img)
        self.canvas2.create_image(0, 0, anchor=tk.NW, image=self.canvas2.image)
        self.canvas2.config(scrollregion=(0, 0, new_width, new_height))

        # Прокручиваем так, чтобы под курсором осталась та же точка
        self.canvas2.xview_moveto((mouse_x * zoom_factor - event.x) / new_width)
        self.canvas2.yview_moveto((mouse_y * zoom_factor - event.y) / new_height)

        # Обновляем статус масштаба
        try:
            self.app.gui.components['status'].update_status(zoom=f"{int(self.state.canvas2_scale * 100)}%")
        except Exception as e:
            logger.debug(f"Ошибка обновления статуса масштаба: {e}")

    def update_coordinates_display(self):
        if hasattr(self.app.gui, 'coordinates_entry'):
            coordinates_text = f"{self.state.x_start},{self.state.y_start},{self.state.x_end},{self.state.y_end}"
            self.app.gui.coordinates_entry.delete(0, tk.END)
            self.app.gui.coordinates_entry.insert(0, coordinates_text)

    def update_cropped_image(self):
        """Обновление увеличенной копии выделенной области на втором холсте"""
        if not self.state.page_image:
            logger.warning("Нет page_image для обновления обрезанного изображения")
            return

        try:
            logger.debug("=== НАЧАЛО update_cropped_image ===")

            # Логируем исходные координаты и масштаб
            logger.debug(
                f"Исходные координаты: ({self.state.x_start}, {self.state.y_start}) - ({self.state.x_end}, {self.state.y_end})")
            logger.debug(f"Текущий scale_factor: {self.state.scale_factor}")

            # Вырезаем область с оригинальными координатами (без учета текущего масштаба)
            inverse_scale = 1 / self.state.scale_factor
            x1 = int(self.state.x_start * inverse_scale)
            y1 = int(self.state.y_start * inverse_scale)
            x2 = int(self.state.x_end * inverse_scale)
            y2 = int(self.state.y_end * inverse_scale)

            logger.debug(f"Координаты после пересчета: ({x1}, {y1}) - ({x2}, {y2})")
            logger.debug(f"inverse_scale: {inverse_scale}")

            # Проверяем валидность координат
            if x2 <= x1:
                logger.error(f"Некорректные X координаты: x1={x1}, x2={x2}")
                return
            if y2 <= y1:
                logger.error(f"Некорректные Y координаты: y1={y1}, y2={y2}")
                return

            # Вырезаем из оригинального изображения
            if self.state.original_page_image:
                logger.debug("Используем original_page_image для вырезки")
                original_width, original_height = self.state.original_page_image.size
                logger.debug(f"Размер оригинального изображения: {original_width}x{original_height}")

                # Проверяем границы
                x1 = max(0, min(x1, original_width - 1))
                y1 = max(0, min(y1, original_height - 1))
                x2 = max(1, min(x2, original_width))
                y2 = max(1, min(y2, original_height))

                logger.debug(f"Координаты после проверки границ: ({x1}, {y1}) - ({x2}, {y2})")

                if x2 <= x1 or y2 <= y1:
                    logger.error(f"Координаты вышли за границы после нормализации")
                    return

                self.state.cropped_image = self.state.original_page_image.crop((x1, y1, x2, y2))
                logger.debug(f"Вырезано из оригинала: {self.state.cropped_image.size}")
            else:
                logger.debug("Используем page_image для вырезки (оригинала нет)")
                page_width, page_height = self.state.page_image.size
                logger.debug(f"Размер page_image: {page_width}x{page_height}")

                # Проверяем границы для масштабированного изображения
                x1_scaled = max(0, min(self.state.x_start, page_width - 1))
                y1_scaled = max(0, min(self.state.y_start, page_height - 1))
                x2_scaled = max(1, min(self.state.x_end, page_width))
                y2_scaled = max(1, min(self.state.y_end, page_height))

                logger.debug(
                    f"Координаты для масштабированного изображения: ({x1_scaled}, {y1_scaled}) - ({x2_scaled}, {y2_scaled})")

                self.state.cropped_image = self.state.page_image.crop((
                    x1_scaled, y1_scaled,
                    x2_scaled, y2_scaled
                ))
                logger.debug(f"Вырезано из масштабированного: {self.state.cropped_image.size}")

            # Проверяем результат вырезки
            if not self.state.cropped_image:
                logger.error("Не удалось создать cropped_image")
                return

            cropped_width, cropped_height = self.state.cropped_image.size
            logger.debug(f"Размер cropped_image: {cropped_width}x{cropped_height}")

            if cropped_width == 0 or cropped_height == 0:
                logger.error("Вырезанное изображение имеет нулевой размер")
                return

            # Подготавливаем изображение для отображения
            canvas2_scale = 1.0
            self.state.canvas2_scale = canvas2_scale
            width = int(cropped_width * canvas2_scale)
            height = int(cropped_height * canvas2_scale)

            logger.debug(f"Масштаб для canvas2: {canvas2_scale}")
            logger.debug(f"Размер после масштабирования: {width}x{height}")

            # Масштабируем изображение
            scaled_img = self.state.cropped_image.resize((width, height), Image.LANCZOS)
            logger.debug("Изображение масштабировано")

            # Отображаем на canvas2
            self.canvas2.delete("all")
            logger.debug("Canvas2 очищен")

            self.canvas2.image = ImageTk.PhotoImage(scaled_img)
            logger.debug("Создан PhotoImage для canvas2")

            self.canvas2.create_image(0, 0, anchor=tk.NW, image=self.canvas2.image)
            logger.debug("Изображение создано на canvas2")

            self.canvas2.config(scrollregion=self.canvas2.bbox(tk.ALL))
            logger.debug("Область прокрутки установлена")

            logger.debug(f"УСПЕШНО: Обновлено изображение на втором холсте: {width}x{height}")
            logger.debug("=== КОНЕЦ update_cropped_image ===")

        except Exception as e:
            logger.error(f"ОШИБКА в update_cropped_image: {e}")
            logger.debug("=== КОНЕЦ update_cropped_image С ОШИБКОЙ ===")


    def draw_selection(self):
        """Рисование выделенной области и обновление второго холста"""
        if self.state.rect_id:
            self.canvas.delete(self.state.rect_id)

        self.state.rect_id = self.canvas.create_rectangle(
            self.state.x_start, self.state.y_start,
            self.state.x_end, self.state.y_end,
            outline="red", width=2
        )
        self.update_coordinates_display()
        self.update_cropped_image()  # Обязательно обновляем второй холст


class TableComponent:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.state = app.state
        self.tree = None
        self.last_click_time = 0
        self._prevent_selection_loop = False  # Добавляем флаг

    def create_table(self):
        table_frame = ttk.Frame(self.parent)
        table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(table_frame, yscrollcommand=tree_scroll.set, selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)

        self.tree["columns"] = ("number", "expected", "invoice", "recognized", "match", "score")
        self.tree.column("#0", width=0, stretch=tk.NO)
        self.tree.column("number", width=60, anchor=tk.CENTER)
        self.tree.column("expected", width=0, minwidth=0, stretch=tk.NO)
        self.tree.column("invoice", width=0, stretch=tk.NO)
        self.tree.column("recognized", width=170, anchor=tk.W)
        self.tree.column("match", width=170, anchor=tk.W)
        self.tree.column("score", width=80, anchor=tk.CENTER)

        self.tree.heading("number", text="№")
        self.tree.heading("expected", text="Контейнер из XLS")
        self.tree.heading("invoice", text="Накладная (XLS)")
        self.tree.heading("recognized", text="Контейнер распознанный")
        self.tree.heading("match", text="Совпадение")
        self.tree.heading("score", text="Коэффициент")

        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Return>", self.on_tree_enter)
        # self.tree.bind("<<TreeviewSelect>>", self.on_tree_selection_change)

        return self.tree

    def on_tree_click(self, event):
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
            if column == "#5":  # Столбец "Совпадение"
                self.edit_cell(item, column)
            elif column == "#4":  # Столбец "Контейнер распознанный"
                self.copy_recognized_to_clipboard(item, event)


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

        if getattr(self.app.gui, "_programmatic_selection", False):
            return
        current_selection = self.tree.selection()
        if current_selection:
            self.goto_page(current_selection[0])

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
        """Редактирование ячейки таблицы"""
        expected_containers = []
        for xls_id, container in self.state.all_excel_records:
            if container and container not in expected_containers:
                expected_containers.append(container)

        expected_containers.sort()

        # Получаем координаты и текущее значение
        x, y, width, height = self.tree.bbox(item, column)
        current_value = self.tree.item(item, "values")[4]  # столбец "Совпадение"

        # Создаем поле ввода
        first_input = {"done": False}
        entry_edit = tk.Entry(self.tree, borderwidth=0, font=("Arial", 10))
        entry_edit.place(x=x, y=y, width=width, height=height, anchor=tk.NW)
        entry_edit.insert(0, current_value)
        entry_edit.focus_set()

        # Создаем Listbox для автоподсказок
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
                if event.char and len(event.char) == 1:
                    char = event.char.upper()
                    entry_edit.delete(0, tk.END)
                    entry_edit.insert(0, char)
                    entry_edit.icursor(1)
                    first_input["done"] = True
                    update_listbox()
                return

            if event.keysym in ("Up", "Down", "Return"):
                return

            # Преобразуем в верхний регистр
            pos = entry_edit.index(tk.INSERT)
            text = entry_edit.get().upper()
            entry_edit.delete(0, tk.END)
            entry_edit.insert(0, text)
            entry_edit.icursor(pos)
            update_listbox()

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
                self.tree.focus(item)
                self.tree.selection_set(item)
                self.tree.see(item)
                self.tree.focus_set()
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
                self.tree.focus(item)
                self.tree.selection_set(item)
                self.tree.see(item)
                self.tree.focus_set()
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

            # Обновляем цвет для ручного редактирования
            self.tree.tag_configure("manual_edit", background="#ddaaff")
            self.tree.item(item, tags=("manual_edit",))

            self.tree.item(item, values=values)
            entry_edit.destroy()
            listbox.place_forget()

        def on_entry_focus_out(event):
            widget = event.widget.focus_get()
            if widget != listbox:
                save_edit()

        # Привязки событий
        entry_edit.bind("<KeyRelease>", on_key_release)
        entry_edit.bind("<FocusOut>", on_entry_focus_out)
        entry_edit.bind("<KeyPress>", on_entry_key)
        listbox.bind("<<ListboxSelect>>", on_listbox_select)
        listbox.bind("<Return>", on_listbox_key)
        listbox.bind("<Escape>", on_listbox_key)
        listbox.bind("<Double-Button-1>", on_listbox_select)
        listbox.bind("<FocusOut>", lambda e: listbox.place_forget())
        update_listbox()

    # gui/components.py (добавляем в класс TableComponent)
    def bind_navigation_keys(self):
        """Привязка клавиш навигации"""
        self.tree.bind("<Up>", self.on_arrow_key)
        self.tree.bind("<Down>", self.on_arrow_key)
        self.tree.bind("<Home>", self.on_arrow_key)
        self.tree.bind("<End>", self.on_arrow_key)
        self.tree.bind("<Prior>", self.on_arrow_key)  # Page Up
        self.tree.bind("<Next>", self.on_arrow_key)  # Page Down

    def on_arrow_key(self, event):
        """Обработчик клавиш навигации"""

        # Позволяем стандартную обработку навигации по таблице
        # После чего обновляем страницу PDF
        def update_after_navigation():
            current_selection = self.tree.selection()
            if current_selection:
                self.goto_page(current_selection[0])

        # Вызываем обновление после завершения стандартной обработки
        self.tree.after(10, update_after_navigation)

class StatusBar:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.state = app.state

        self.status_page_var = tk.StringVar(value="Стр: —/—")
        self.status_zoom_var = tk.StringVar(value="Масштаб: 100%")
        self.status_size_var = tk.StringVar(value="Размер: —×—")
        self.status_msg_var = tk.StringVar(value="Готово")

    def create_statusbar(self):
        statusbar = ttk.Frame(self.parent, style="Toolbar.TFrame")
        statusbar.pack(side=tk.BOTTOM, fill="x")

        ttk.Label(statusbar, textvariable=self.status_page_var).pack(side=tk.LEFT, padx=8, pady=4)
        ttk.Label(statusbar, text="|").pack(side=tk.LEFT, padx=6)
        ttk.Label(statusbar, textvariable=self.status_zoom_var).pack(side=tk.LEFT, padx=8)
        ttk.Label(statusbar, text="|").pack(side=tk.LEFT, padx=6)
        ttk.Label(statusbar, textvariable=self.status_size_var).pack(side=tk.LEFT, padx=8)
        ttk.Label(statusbar, textvariable=self.status_msg_var).pack(side=tk.RIGHT, padx=8)

    def update_status(self, page=None, total=None, zoom=None, size=None, msg=None):
        if page is not None and total is not None:
            self.status_page_var.set(f"Стр: {page}/{total}")
        if zoom is not None:
            self.status_zoom_var.set(f"Масштаб: {zoom}")
        if size is not None:
            self.status_size_var.set(f"Размер: {size}")
        if msg is not None:
            self.status_msg_var.set(msg)
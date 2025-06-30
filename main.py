import csv
import logging
import os
import re
import sys
import threading
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk

import cv2
import fitz  # PyMuPDF
import numpy as np
import openpyxl  # для .xlsx
import pytesseract
import requests
from PIL import Image, ImageTk
from dotenv import load_dotenv, set_key

from version import __version__  # Импортируем номер версии

EASYOCR_AVAILABLE = False
PADDLEOCR_AVAILABLE = False


# Глобальные переменные (лучше использовать класс для состояния)
DEFAULT_COORDINATES2 = {
    "x_start": 20,
    "y_start": 298,
    "x_end": 92,
    "y_end": 345,
    "regex_pattern": "^[A-Z]{3}U\d{7}$",
}

global table_frame, debug_mode

original_page_image = None
pdf_path = None
image_display = None
rect_id = None
text_output = None
# pdf = None
pdf_doc = None
scale_percent = 100  # Масштаб для обработки координат
ENV_FILE = ".env"

# reader = None
# Добавьте в раздел глобальных переменных
ocr_engine = "Tesseract"  # По умолчанию
ocr_reader = None  # Для хранения инициализированного ридера EasyOCR/PaddleOCR
current_page = 0
canvas_scale = 1.0

table_entries = []  # глобальная переменная — таблица как список словарей
expected_containers = []  # список контейнеров из XLS
selected_areas = []
recognition_results = []  # Будет хранить словари с результатами для каждой страницы
last_click_time = 0
DOUBLE_CLICK_DELAY = 300  # Задержка для двойного клика в миллисекундах


# Настройка логирования
logging.basicConfig(
    filename="app.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)



def is_similar_ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


def match_with_expected():
    global table_entries, expected_containers, tree

    # Получаем ожидаемые контейнеры из таблицы
    expected_containers = []
    for item in tree.get_children():
        values = tree.item(item, 'values')
        if len(values) > 1 and values[1]:  # values[1] - столбец "Контейнер из XLS"
            expected_containers.append(values[1])

    if not expected_containers:
        messagebox.showwarning("Ошибка", "Нет данных для сопоставления в столбце 'Контейнер из XLS'")
        return

    for entry in table_entries:
        recognized = entry.get("recognized", "")
        if not recognized:
            continue

        best_match = ""
        best_score = 0.0

        for expected in expected_containers:
            if not expected:
                continue
            score = is_similar_ratio(recognized, expected)
            if score > best_score:
                best_score = score
                best_match = expected

        # Обновляем строку в таблице
        values = list(tree.item(entry["item_id"], 'values'))
        values[3] = best_match  # Совпадение
        values[4] = f"{best_score:.2f}"  # Коэффициент
        tree.item(entry["item_id"], values=values)

        # Обновляем цвет строки
        if best_score == 1.0:  # Полное совпадение
            tree.tag_configure("exact_match", background="#a8e6a8")  # Светло-зеленый
            tree.item(entry["item_id"], tags=("exact_match",))
        elif best_score > 0:  # Любое другое совпадение
            tree.tag_configure("partial_match", background="#fff8a8")  # Светло-желтый
            tree.item(entry["item_id"], tags=("partial_match",))
        else:  # Нет совпадения
            tree.tag_configure("no_match", background="#ffaaaa")  # Светло-красный
            tree.item(entry["item_id"], tags=("no_match",))

def safe_execute(func):
    """Декоратор для оборачивания функций с обработкой ошибок и логированием."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Ошибка в функции {func.__name__}: {e}", exc_info=True)
            messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")

    return wrapper


def set_tesseract_path():
    # Список возможных путей установки Tesseract
    possible_paths = [
        r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
        os.path.expanduser(r"~\\Tesseract-OCR\\tesseract.exe"),
        os.path.expanduser(r"~\\AppData\\Local\\Tesseract-OCR\\tesseract.exe"),
        os.path.expanduser(
            r"~\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe"
        ),
    ]
    # Проверка пути в папке Programs

    # Проверка всех возможных путей
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            # print(f"Путь для Tesseract установлен: {path}")
            return

    # Если ни один путь не найден
    print("Tesseract не найден. Пожалуйста, установите его по ссылке:")
    print("https://github.com/UB-Mannheim/tesseract/wiki")


# Функция для создания выходной папки
def create_output_directory(input_file_path):
    try:
        base_name = os.path.splitext(os.path.basename(input_file_path))[0]
        output_dir = f"{base_name}_out"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        return output_dir
    except OSError as e:
        messagebox.showerror("Ошибка", f"Не удалось создать выходную папку: {e}")
        return None



def draw_selection():
    global rect_id, x_start, y_start, x_end, y_end, canvas2, cropped_image, canvas2_scale

    if rect_id:
        canvas.delete(rect_id)
    rect_id = canvas.create_rectangle(
        x_start, y_start, x_end, y_end, outline="red", width=2
    )

    update_coordinates_entry()

    if page_image:
        # Вырезаем область с оригинальными координатами (без учета текущего масштаба)
        inverse_scale = 1 / scale_factor
        x1 = int(x_start * inverse_scale)
        y1 = int(y_start * inverse_scale)
        x2 = int(x_end * inverse_scale)
        y2 = int(y_end * inverse_scale)

        cropped_image = original_page_image.crop((x1, y1, x2, y2))

        # Масштабируем до 200% по умолчанию
        canvas2_scale = 1.0
        width = int(cropped_image.width * canvas2_scale)
        height = int(cropped_image.height * canvas2_scale)
        scaled_img = cropped_image.resize((width, height), Image.LANCZOS)

        # Отображаем на canvas2
        canvas2.delete("all")
        canvas2.image = ImageTk.PhotoImage(scaled_img)
        canvas2.create_image(0, 0, anchor=tk.NW, image=canvas2.image)
        canvas2.config(scrollregion=canvas2.bbox(tk.ALL))


def unload_pdf():
    global pdf_doc, current_page, page_image, image_display
    global original_page_image, selected_areas, total_pages
    global scale_factor, last_scale_factor

    try:
        if pdf_doc:
            pdf_doc.close()
            pdf_doc = None
    except Exception as e:
        logging.warning(f"Не удалось закрыть PDF: {e}")

    # Сброс параметров
    current_page = 0
    page_image = None
    original_page_image = None
    image_display = None
    selected_areas = []
    total_pages = 0
    scale_factor = 1.0
    last_scale_factor = 1.0

    # Очистка холста
    if canvas:
        canvas.delete("all")
        canvas.config(scrollregion=(0, 0, 0, 0))


def select_pdf():
    global pdf_path, current_page, entry_pdf_path
    try:
        file_path = filedialog.askopenfilename(filetypes=[("PDF файлы", "*.pdf")])
        if file_path:
            unload_pdf()  # ← сбрасываем предыдущий
            pdf_path = file_path

            entry_pdf_path.delete(0, tk.END)
            entry_pdf_path.insert(0, file_path)
            current_page = 0

            load_page()
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось выбрать или загрузить PDF: {e}")
        logging.exception("Ошибка выбора PDF")



# Функция загрузки и отображения страницы PDF
@safe_execute
def load_page():
    global image_display, label_page_number, label_page_size, label_scale
    global pdf_doc, current_page, page_image, scale_factor
    global page_width2, page_height2, canvas, total_pages
    global original_page_image, last_scale_factor, pdf_path, tree

    if not pdf_path:
        return

    try:
        if pdf_doc is None:
            recognition_results = []  # Очищаем предыдущие результаты
            pdf_doc = fitz.open(pdf_path)
            # Создаем строки таблицы по количеству страниц
            build_table_from_pdf(pdf_doc)

        current_page = max(0, min(current_page, pdf_doc.page_count - 1))
        page = pdf_doc.load_page(current_page)
        total_pages = pdf_doc.page_count

        pix = page.get_pixmap(dpi=200)
        original_page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        canvas_height = canvas.winfo_height()
        image_height = original_page_image.height
        scale_factor = (scale_percent / 100) * (canvas_height / image_height)
        last_scale_factor = scale_factor

        scaled_width = int(original_page_image.width * scale_factor)
        scaled_height = int(original_page_image.height * scale_factor)
        page_image = original_page_image.resize((scaled_width, scaled_height), Image.LANCZOS)

        image_display = ImageTk.PhotoImage(image=page_image)
        if canvas:
            canvas.delete("all")
            canvas.create_image(0, 0, anchor=tk.NW, image=image_display)
            canvas.config(scrollregion=canvas.bbox(tk.ALL))

        root.title(f"Распознавание текста из PDF - Страница {current_page + 1}/{total_pages}")
        draw_selection()

    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось загрузить страницу: {e}")
        logging.exception("Ошибка при загрузке страницы")

# Функция для выбора координат области
def define_coordinates(event):
    global x_start, y_start, rect_id, scale_percent, scale_factor
    # Координаты события с учетом масштаба
    x_start = int(event.x)
    y_start = int(event.y)
    print(scale_factor)
    print(scale_percent)
    print(event.x, event.y)
    print(x_start, y_start)

    # Удаляем старое выделение, если оно есть
    if rect_id:
        canvas.delete(rect_id)

    # Создаем новый прямоугольник, начальная точка
    rect_id = canvas.create_rectangle(
        x_start, y_start, x_start, y_start, outline="red", width=2
    )
    update_coordinates_entry()


def draw_rectangle(event):
    global rect_id, x_start, y_start
    x_end, y_end = event.x, event.y
    if rect_id is not None:
        canvas.coords(rect_id, x_start, y_start, x_end, y_end)


def finish_coordinates(event):
    global x_start, y_start, x_end, y_end, cropped_image_display, cropped_image
    global canvas2, label_coordinates, total_pages

    x_end, y_end = event.x, event.y

    # Проверяем, чтобы координаты были корректны
    if x_end < x_start:
        x_start, x_end = x_end, x_start
    if y_end < y_start:
        y_start, y_end = y_end, y_start

    root.title(
        f"Распознавание текста из PDF - Страница {current_page + 1}/{total_pages} - Координаты: ({x_start}, {y_start}) -> ({x_end}, {y_end})")

    canvas.coords(rect_id, x_start, y_start, x_end, y_end)
    selected_areas.clear()
    selected_areas.append((rect_id, x_start, y_start, x_end, y_end))

    update_coordinates_entry()

    if page_image:
        try:
            cropped_image = page_image.crop((x_start, y_start, x_end, y_end))
            cropped_image_display = ImageTk.PhotoImage(image=cropped_image)
            canvas2.create_image(0, 0, anchor=tk.NW, image=cropped_image_display)
            canvas2.image = cropped_image_display
        except Exception as e:
            messagebox.showerror("Ошибка", f"Неверные координаты выделения: {e}")

# Функция обновления метки координат
def update_coordinates_label():
    global x_start, y_start, x_end, y_end, label_coordinates
    if (
        x_start is not None
        and y_start is not None
        and x_end is not None
        and y_end is not None
    ):
        label_coordinates.config(
            text=f"Координаты: x={x_start}, y={y_start}, width={x_end - x_start}, height={y_end - y_start}"
        )


def update_coordinates_entry():
    global x_start, y_start, x_end, y_end, coordinates_entry
    if (
        x_start is not None
        and y_start is not None
        and x_end is not None
        and y_end is not None
    ):
        coordinates_text = f"{x_start},{y_start},{x_end},{y_end}"
        coordinates_entry.delete(0, tk.END)
        coordinates_entry.insert(0, coordinates_text)


# Функция для проверки и форматирования распознанного текста
def format_extracted_text(text, i):
    # Удаление всех символов, кроме английских букв и цифр
    cleaned_text = re.sub(r"[^A-Za-z0-9]", "", text).upper()

    # Проверка формата: 4 буквы (в верхнем регистре) + 7 цифр
    if re.match(r"^[A-Z]{4}\d{7}$", cleaned_text):
        return cleaned_text

    # Замена неправильных символов на '@'
    formatted_text = ""
    for i, char in enumerate(cleaned_text):
        if i < 4 and not char.isalpha():
            formatted_text += "@"
        elif i < 4 and char.islower():
            formatted_text += char.upper()
        elif i >= 4 and not char.isdigit():
            formatted_text += "@"
        else:
            formatted_text += char

    # Проверка длины результата и обрезка лишнего
    formatted_text = formatted_text[
        :11
    ]  # Убедиться, что длина не превышает 11 символов

    # Дополнение '@', если строка короче
    while len(formatted_text) < 11:
        formatted_text += "@"

    return formatted_text


def build_table_from_pdf(pdf_doc):
    global table_entries, tree

    # Очищаем таблицу
    for item in tree.get_children():
        tree.delete(item)

    table_entries = []

    # Создаем строки по количеству страниц
    for i in range(pdf_doc.page_count):
        item_id = tree.insert("", tk.END, values=(
            i + 1,  # № страницы
            "",  # Контейнер из XLS (пока пусто)
            "",  # Распознанный контейнер
            "",  # Совпадение
            ""  # Коэффициент
        ))
        table_entries.append({
            "index": i + 1,
            "item_id": item_id,
            "code": "",
            "recognized": ""
        })

def update_table_from_entries(table_frame_ref):
    global table_entries

    # Очистка предыдущего содержимого таблицы
    for widget in table_frame_ref.grid_slaves():
        if int(widget.grid_info()["row"]) > 0:
            widget.destroy()

    for i, entry in enumerate(table_entries, start=1):
        # Ячейка "№"
        tk.Label(table_frame_ref, text=str(entry["index"]), borderwidth=1, relief=tk.RIDGE).grid(row=i, column=0, sticky="nsew")

        # Ячейка "Контейнер из XLS" — может быть пустой
        tk.Label(table_frame_ref, text=entry.get("code", ""), borderwidth=1, relief=tk.RIDGE).grid(row=i, column=1, sticky="nsew")

        # Ячейка "Контейнер распознанный"
        lbl_recognized = tk.Label(table_frame_ref, text=entry.get("recognized", ""), borderwidth=1, relief=tk.RIDGE)
        lbl_recognized.grid(row=i, column=2, sticky="nsew")
        entry["label_recognized"] = lbl_recognized

        # Ячейка "Совпадение"
        lbl_match = tk.Label(table_frame_ref, text=entry.get("match", ""), borderwidth=1, relief=tk.RIDGE)
        lbl_match.grid(row=i, column=3, sticky="nsew")
        entry["label_match"] = lbl_match

        # Ячейка "Коэффициент"
        lbl_score = tk.Label(table_frame_ref, text=entry.get("score", ""), borderwidth=1, relief=tk.RIDGE)
        lbl_score.grid(row=i, column=4, sticky="nsew")
        entry["label_score"] = lbl_score


# Функция для выполнения длительной задачи в потоке
def start_recognition_thread():
    threading.Thread(target=start_recognition, daemon=True).start()

def start_recognition2():
    global selected_areas, pdf_doc, tree

    if not pdf_doc:
        messagebox.showwarning("Нет документа", "Пожалуйста, выберите PDF-файл.")
        return

    # Если нет выделенной области, но есть координаты из .env
    if not selected_areas and all(v is not None for v in [x_start, y_start, x_end, y_end]):
        selected_areas = [(None, x_start, y_start, x_end, y_end)]
        draw_selection()  # Визуализируем область


    if not selected_areas:
        messagebox.showwarning("Нет выделения", "Пожалуйста, выделите область на холсте.")
        return

    area = selected_areas[0]
    _, x1, y1, x2, y2 = area
    coords = (x1, y1, x2, y2)
    engine = ocr_engine_var.get().lower()

    text_output.delete(1.0, tk.END)
    text_output.insert(tk.END, "Начало распознавания...\n")
    text_output.see(tk.END)
    root.update()  # Обновляем интерфейс, чтобы показать сообщение

    try:
        for page_num in range(pdf_doc.page_count):
            try:
                recognized_text = recognize_area(pdf_doc, page_num, coords, engine)
                formatted_text = format_extracted_text(recognized_text, page_num + 1)

                # Обновляем таблицу
                if page_num < len(table_entries):
                    table_entries[page_num]["recognized"] = formatted_text
                    tree.item(table_entries[page_num]["item_id"],
                             values=(
                                 page_num + 1,
                                 table_entries[page_num]["code"],
                                 formatted_text,
                                 "",  # Совпадение
                                 ""   # Коэффициент
                             ))

                # Логируем прогресс
                log_msg = f"Страница {page_num + 1}/{pdf_doc.page_count}: {formatted_text}\n"
                text_output.insert(tk.END, log_msg)
                text_output.see(tk.END)
                root.update()  # Обновляем интерфейс после каждой страницы

            except Exception as e:
                error_msg = f"Ошибка на странице {page_num + 1}: {str(e)}\n"
                text_output.insert(tk.END, error_msg)
                text_output.see(tk.END)
                logging.error(error_msg, exc_info=True)
                continue

        text_output.insert(tk.END, "\nРаспознавание завершено!\n")
        logging.info(f"Распознано {pdf_doc.page_count} страниц.")

    except Exception as e:
        error_msg = f"Критическая ошибка: {str(e)}\n"
        text_output.insert(tk.END, error_msg)
        logging.error(error_msg, exc_info=True)
        logging.error(f"Произошла ошибка при распознавании: {e}")


def start_recognition():
    global selected_areas, pdf_doc, last_scale_factor

    if not pdf_doc:
        messagebox.showwarning("Нет документа", "Пожалуйста, выберите PDF-файл.")
        return

    # Если нет выделенной области, но есть координаты из .env
    if not selected_areas and all(v is not None for v in [x_start, y_start, x_end, y_end]):
        selected_areas = [(None, x_start, y_start, x_end, y_end)]
        draw_selection()  # Визуализируем область


    if not selected_areas:
        messagebox.showwarning("Нет выделения", "Пожалуйста, выделите область на холсте.")
        return

    try:
        area = selected_areas[0]
        _, x1, y1, x2, y2 = area
        coords = (x1, y1, x2, y2)
        engine = ocr_engine_var.get().lower()

        for page_num in range(pdf_doc.page_count):
            recognized_text = recognize_area(pdf_doc, page_num, coords, engine)
            formatted_text = format_extracted_text(recognized_text, page_num + 1)

            # Обновляем таблицу
            if page_num < len(table_entries):
                table_entries[page_num]["recognized"] = formatted_text
                item_id = table_entries[page_num]["item_id"]
                current_values = list(tree.item(item_id, 'values'))
                current_values[2] = formatted_text  # recognized column
                tree.item(item_id, values=current_values)

        messagebox.showinfo("Готово", f"Распознано {pdf_doc.page_count} страниц.")

    except Exception as e:
        logging.exception("Ошибка при распознавании всех страниц")
        messagebox.showerror("Ошибка", f"Произошла ошибка при распознавании: {e}")




def save_results(btn):
    """Запускает сохранение результатов в отдельном потоке"""
    btn.config(state=tk.DISABLED)
    threading.Thread(target=_save_results_worker, args=(btn,), daemon=True).start()


def _save_results_worker(btn):
    """Функция-рабочий для сохранения результатов"""
    global pdf_doc, table_entries, debug_mode, recognition_results

    if not pdf_doc:
        messagebox.showerror("Ошибка", "PDF документ не загружен")
        return

    if not table_entries:
        messagebox.showerror("Ошибка", "Нет данных для сохранения")
        return

    try:
        # Создаем прогресс-бар
        progress = tk.Toplevel(root)
        progress.title("Сохранение...")
        progress.geometry("300x100")
        tk.Label(progress, text="Идет сохранение результатов").pack(pady=10)
        progress_bar = ttk.Progressbar(progress, mode='indeterminate')
        progress_bar.pack(fill='x', padx=20, pady=5)
        progress_bar.start()

        # Выполняем сохранение в потоке
        output_dir = create_output_directory(pdf_path)

        for i, entry in enumerate(table_entries):
            page_num = entry['index'] - 1
            page = pdf_doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            recognized = entry.get('recognized', '')
            match = tree.item(entry['item_id'], 'values')[3]  # Значение из столбца "Совпадение"
            filename = match if match else recognized if recognized else f"page_{i + 1}"

            base_path = os.path.join(output_dir, f"{i + 1}_{filename}")
            page_image.save(f"{base_path}_full.jpg")

            if debug_mode.get():
                if hasattr(canvas2, 'image') and canvas2.image:
                    cropped_image.save(f"{base_path}_cropped.jpg")

                if i < len(recognition_results):
                    result = recognition_results[i]
                    with open(f"{base_path}_info.txt", "w", encoding="utf-8") as f:
                        f.write(f"Страница: {result['page']}\n")
                        f.write(f"Координаты: {result['coords']}\n")
                        f.write(f"Движок OCR: {result['engine']}\n")
                        f.write("\n--- Исходный текст ---\n")
                        f.write(result['raw_text'])
                        f.write("\n\n--- Форматированный текст ---\n")
                        f.write(result['formatted_text'])

                # with open(f"{base_path}.txt", "w", encoding="utf-8") as f:
                #     f.write(recognized)

        # Закрываем прогресс-бар и показываем сообщение
        progress.destroy()
        messagebox.showinfo("Сохранено", f"Результаты сохранены в папку:\n{output_dir}")

    except Exception as e:
        progress.destroy()
        messagebox.showerror("Ошибка", f"Ошибка при сохранении: {str(e)}")
        logging.error(f"Ошибка сохранения: {e}", exc_info=True)
    finally:
        if 'progress' in locals():
            progress.destroy()
        btn.after(0, lambda: btn.config(state=tk.NORMAL))


def _save_results_worker3():
    global recognition_results

    try:
        output_dir = create_output_directory(pdf_path)

        for i, entry in enumerate(table_entries):
            page_num = entry['index'] - 1
            page = pdf_doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            base_path = os.path.join(output_dir, f"page_{i + 1}")
            page_image.save(f"{base_path}_full.jpg")

            # Сохранение дополнительных данных в debug-режиме
            if debug_mode.get():
                # Сохраняем cropped image
                if hasattr(canvas2, 'image') and canvas2.image:
                    cropped_image.save(f"{base_path}_cropped.jpg")

                # Сохраняем распознанный текст
                if i < len(recognition_results):
                    result = recognition_results[i]
                    with open(f"{base_path}_info.txt", "w", encoding="utf-8") as f:
                        f.write(f"Страница: {result['page']}\n")
                        f.write(f"Координаты: {result['coords']}\n")
                        f.write(f"Движок OCR: {result['engine']}\n")
                        f.write("\n--- Исходный текст ---\n")
                        f.write(result['raw_text'])
                        f.write("\n\n--- Форматированный текст ---\n")
                        f.write(result['formatted_text'])

        messagebox.showinfo("Сохранено", f"Результаты сохранены в папку:\n{output_dir}")

    except Exception as e:
        messagebox.showerror("Ошибка", f"Ошибка при сохранении: {str(e)}")
        logging.error(f"Ошибка сохранения: {e}", exc_info=True)



def recognize_with_selected_engine2(image):

    if ocr_engine == "tesseract":
        return pytesseract.image_to_string(image, lang="eng").strip()

    if ocr_engine == "easyocr":
        results = ocr_reader.readtext(image, detail=0, paragraph=False)
        return " ".join(results).strip()

    if ocr_engine == "paddleocr":
        results = ocr_reader.predict(img=image, cls=True)
        if results and isinstance(results[0], list):
            texts = [line[1][0] for line in results[0]]
            return " ".join(texts).strip()
        return ""

    # fallback, если движок неизвестен
    return ""

def run_ocr_in_thread(image, **kwargs):
    """Запуск OCR в отдельном потоке с передачей параметров."""
    threading.Thread(target=enhanced_recognition, args=(image,), kwargs=kwargs).start()


@safe_execute
def enhanced_recognition(
    image,
    use_grayscale=True,
    use_median_blur=True,
    use_thresholding=False,
    use_clahe=True,
    use_resize=True,
    use_deskew=False,
    use_noise_removal=True,
    use_morphological_ops=False,
    use_channel_extraction=False,
    channel="blue",
    use_edge_preprocessing=True  # новый параметр
):
    """Расширенная функция распознавания текста с поддержкой EasyOCR и настройками включения этапов обработки."""

    # Преобразование в оттенки серого
    if use_grayscale:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Предобработка через Canny после размытия
    if use_edge_preprocessing:
        blur = cv2.GaussianBlur(image, (5, 5), 0)
        image = cv2.Canny(blur, 50, 150)

    # Применение медианной фильтрации для удаления шума
    if use_median_blur:
        image = cv2.medianBlur(image, 3)

    # Применение бинаризации и пороговой обработки
    if use_thresholding:
        _, image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Применение CLAHE для повышения контраста
    if use_clahe:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        image = clahe.apply(image)

    # Масштабирование изображения для лучшего распознавания
    if use_resize:
        image = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # Коррекция наклона (deskew)
    if use_deskew:
        coords = np.column_stack(np.where(image > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        image = cv2.warpAffine(
            image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )

    # Удаление шума с помощью морфологических операций
    if use_noise_removal:
        image = cv2.medianBlur(image, 3)

    # Морфологические операции для удаления мелких артефактов
    if use_morphological_ops:
        kernel = np.ones((1, 1), np.uint8)
        image = cv2.dilate(image, kernel, iterations=1)
        image = cv2.erode(image, kernel, iterations=1)

    # Извлечение цветового канала (если включено)
    if use_channel_extraction:
        if channel == "blue":
            image = image[:, :, 0]
        elif channel == "green":
            image = image[:, :, 1]
        elif channel == "red":
            image = image[:, :, 2]

    # extracted_text = pytesseract.image_to_string(image, lang="eng").strip()
    extracted_text = pytesseract.image_to_string(image, lang="eng").strip().upper()

    return extracted_text


def convert_coords_to_pdf(coords_canvas, scale_factor):
    x1, y1, x2, y2 = coords_canvas
    return (
        int(x1 / scale_factor),
        int(y1 / scale_factor),
        int(x2 / scale_factor),
        int(y2 / scale_factor),
    )

def extract_text_by_coords(page_num, coords_canvas):
    if not pdf_doc:
        print("PDF-документ не загружен.")
        return ""

    coords_pdf = convert_coords_to_pdf(coords_canvas, last_scale_factor)

    try:
        page = pdf_doc.load_page(page_num)
        pix = page.get_pixmap(dpi=300)
        pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        cropped = pil_img.crop(coords_pdf)
        return recognize_with_selected_engine(cropped)
    except Exception as e:
        print(f"Ошибка при OCR страницы {page_num + 1}: {e}")
        return ""


def check_image2():
    global pdf_doc, current_page, selected_areas, tree

    if not pdf_doc:
        messagebox.showwarning("Нет файла", "Пожалуйста, выберите PDF-файл.")
        return

    # Если нет выделенной области, но есть координаты из .env
    if not selected_areas and all(v is not None for v in [x_start, y_start, x_end, y_end]):
        selected_areas = [(None, x_start, y_start, x_end, y_end)]
        draw_selection()  # Визуализируем область


    if not selected_areas:
        messagebox.showwarning("Нет выделения", "Пожалуйста, выделите область на холсте.")
        return

    try:
        area = selected_areas[0]
        _, x1, y1, x2, y2 = area
        coords = (x1, y1, x2, y2)
        engine = ocr_engine_var.get().lower()

        # Распознаем только текущую страницу
        recognized_text = recognize_area(pdf_doc, current_page, coords, engine)
        formatted_text = format_extracted_text(recognized_text, current_page + 1)

        # Обновляем соответствующую строку в таблице
        if current_page < len(table_entries):
            table_entries[current_page]["recognized"] = formatted_text
            tree.item(table_entries[current_page]["item_id"],
                      values=(
                          current_page + 1,
                          table_entries[current_page]["code"],
                          formatted_text,
                          "",  # Совпадение
                          ""  # Коэффициент
                      ))

        text_output.delete(1.0, tk.END)
        text_output.insert(tk.END, f"Страница {current_page + 1}:\n")
        text_output.insert(tk.END, f"Распознано: {formatted_text}\n")
        text_output.insert(tk.END, f"Исходный текст: {recognized_text}\n")

    except Exception as e:
        logging.error(f"Ошибка при распознавании страницы {current_page + 1}: {e}", exc_info=True)
        messagebox.showerror("Ошибка", f"Ошибка при распознавании: {e}")


def check_image():
    global current_page, selected_areas, recognition_results

    if not pdf_doc:
        messagebox.showwarning("Нет файла", "Пожалуйста, выберите PDF-файл.")
        return

    # Если нет выделенной области, но есть координаты из .env
    if not selected_areas and all(v is not None for v in [x_start, y_start, x_end, y_end]):
        selected_areas = [(None, x_start, y_start, x_end, y_end)]
        draw_selection()  # Визуализируем область


    if not selected_areas:
        messagebox.showwarning("Нет выделения", "Пожалуйста, выделите область на холсте.")
        return

    try:
        area = selected_areas[0]
        _, x1, y1, x2, y2 = area
        coords = (x1, y1, x2, y2)
        engine = ocr_engine_var.get().lower()

        recognized_text = recognize_area(pdf_doc, current_page, coords, engine)
        formatted_text = format_extracted_text(recognized_text, current_page + 1)

        # Обновляем таблицу
        if current_page < len(table_entries):
            table_entries[current_page]["recognized"] = formatted_text
            tree.item(table_entries[current_page]["item_id"],
                      values=(
                          current_page + 1,
                          table_entries[current_page]["code"],
                          formatted_text,
                          "",
                          ""
                      ))

        # Выводим в текстовое поле
        text_output.delete(1.0, tk.END)
        if current_page < len(recognition_results):
            result = recognition_results[current_page]
            text_output.insert(tk.END, f"=== Страница {current_page + 1} ===\n")
            text_output.insert(tk.END, f"Координаты: {result['coords']}\n")
            text_output.insert(tk.END, f"Движок: {result['engine']}\n")
            text_output.insert(tk.END, "\n--- Исходный текст ---\n")
            text_output.insert(tk.END, result['raw_text'])
            text_output.insert(tk.END, "\n\n--- Форматированный текст ---\n")
            text_output.insert(tk.END, result['formatted_text'])

    except Exception as e:
        logging.error(f"Ошибка при распознавании страницы {current_page + 1}: {e}", exc_info=True)
        messagebox.showerror("Ошибка", f"Ошибка при распознавании: {e}")

def extract_area_image_from_pdf(pdf_doc, page_index, coords, dpi=200):
    """Вырезает область изображения из PDF по координатам"""
    x_start, y_start, x_end, y_end = coords

    # Проверяем корректность координат
    if x_end <= x_start or y_end <= y_start:
        raise ValueError("Некорректные координаты области выделения")

    page = pdf_doc.load_page(page_index)
    pix = page.get_pixmap(dpi=dpi)
    page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # Пересчёт координат из canvas → оригинальное изображение
    inverse_scale = 1 / last_scale_factor
    x0 = int(x_start * inverse_scale)
    y0 = int(y_start * inverse_scale)
    x1 = int(x_end * inverse_scale)
    y1 = int(y_end * inverse_scale)

    # Проверяем, чтобы координаты не выходили за границы изображения
    x0 = max(0, min(x0, page_image.width - 1))
    y0 = max(0, min(y0, page_image.height - 1))
    x1 = max(1, min(x1, page_image.width))
    y1 = max(1, min(y1, page_image.height))

    if x1 <= x0 or y1 <= y0:
        raise ValueError("Некорректные координаты после масштабирования")

    cropped = page_image.crop((x0, y0, x1, y1))
    if cropped.size[0] == 0 or cropped.size[1] == 0:
        raise ValueError("Выделенная область имеет нулевой размер")

    return cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2BGR)

def recognize_with_selected_engine(image, engine):
    """Распознает текст с использованием выбранного движка OCR"""
    engine = engine.lower().strip()

    if engine == "tesseract":
        return pytesseract.image_to_string(image, lang="eng").strip()

    if engine == "easyocr" and EASYOCR_AVAILABLE:
        results = ocr_reader.readtext(image, detail=0, paragraph=False)
        return " ".join(results).strip()

    if engine == "paddleocr" and PADDLEOCR_AVAILABLE:
        results = ocr_reader.predict(img=image, cls=True)
        if results and isinstance(results[0], list):
            return " ".join([line[1][0] for line in results[0]]).strip()
        return ""

    # Fallback на Tesseract, если движок неизвестен или недоступен
    return pytesseract.image_to_string(image, lang="eng").strip()

def recognize_area2(pdf_doc, page_index, coords, engine):
    try:
        cropped_image = extract_area_image_from_pdf(pdf_doc, page_index, coords)
        if cropped_image is None or cropped_image.size == 0:
            return ""
        return recognize_with_selected_engine(cropped_image, engine)
    except Exception as e:
        logging.error(f"Ошибка при распознавании области: {e}", exc_info=True)
        return ""

def recognize_area(pdf_doc, page_index, coords, engine):
    global recognition_results

    try:
        cropped_image = extract_area_image_from_pdf(pdf_doc, page_index, coords)
        if cropped_image is None or cropped_image.size == 0:
            return ""

        recognized_text = recognize_with_selected_engine(cropped_image, engine)
        formatted_text = format_extracted_text(recognized_text, page_index + 1)

        # Сохраняем результаты
        result = {
            "page": page_index + 1,
            "raw_text": recognized_text,
            "formatted_text": formatted_text,
            "coords": coords,
            "engine": engine
        }

        # Обновляем или добавляем запись
        if len(recognition_results) > page_index:
            recognition_results[page_index] = result
        else:
            recognition_results.append(result)

        # Вывод в консоль (можно закомментировать)
        print(f"Страница {page_index + 1}: {formatted_text}")

        return formatted_text

    except Exception as e:
        logging.error(f"Ошибка при распознавании области: {e}", exc_info=True)
        return ""

# Функция для перехода к следующей странице
def next_page():
    global current_page
    current_page += 1
    load_page()


# Функция для перехода к предыдущей странице
def prev_page():
    global current_page
    current_page -= 1
    load_page()


# Функция увеличения масштаба
# def zoom_in():
#     global scale_percent
#     scale_percent += 10  # Увеличиваем на 10%
#     load_page()  # Перезагружаем страницу с новым масштабом
# Функция уменьшения масштаба
# def zoom_out():
#     global scale_percent
#     if scale_percent > 10:  # Уменьшаем на 10% минимум
#         scale_percent -= 10
#         load_page()  # Перезагружаем страницу с новым масштабом


# Функция для обновления поля с дефолтными координатами
def set_default_coordinates(coordinates_entry):
    coordinates_text = f"{DEFAULT_COORDINATES2['x_start']},{DEFAULT_COORDINATES2['y_start']},{DEFAULT_COORDINATES2['x_end']},{DEFAULT_COORDINATES2['y_end']}"
    # coordinates_text = f"{DEFAULT_COORDINATES[0]},{DEFAULT_COORDINATES[1]},{DEFAULT_COORDINATES[2]},{DEFAULT_COORDINATES[3]}"
    coordinates_entry.delete(0, tk.END)
    coordinates_entry.insert(0, coordinates_text)


# Функция для проверки формата координат
def validate_coordinates_format(coordinates_text):
    parts = coordinates_text.split(",")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        return True
    return False


def zoom_canvas(event):
    global canvas_scale, canvas, original_page_image, cropped_image_display

    # Увеличение при прокрутке вверх, уменьшение — при прокрутке вниз
    zoom_factor = 1.1 if event.delta > 0 else 0.9
    canvas_scale *= zoom_factor

    # Проверка: изображение должно быть загружено
    if original_page_image:
        # Вычисляем новые размеры
        new_width = int(original_page_image.width * canvas_scale)
        new_height = int(original_page_image.height * canvas_scale)

        # Масштабируем изображение
        scaled_image = original_page_image.resize((new_width, new_height), Image.LANCZOS)

        # Отображаем на холсте
        cropped_image_display = ImageTk.PhotoImage(image=scaled_image)
        canvas.delete("all")  # Очищаем холст перед отрисовкой
        canvas.create_image(0, 0, anchor=tk.NW, image=cropped_image_display)
        canvas.image = cropped_image_display  # Сохраняем ссылку, чтобы не удалялось
        canvas.config(scrollregion=canvas.bbox(tk.ALL))  # Обновляем область прокрутки








def zoom_canvas2(event):
    global canvas2_scale, cropped_image

    try:
        if not hasattr(canvas2, 'image') or not canvas2.image or not cropped_image:
            return

        zoom_factor = 1.1 if event.delta > 0 else 0.9
        new_scale = canvas2_scale * zoom_factor

        # Ограничиваем масштаб между 50% и 500%
        new_scale = max(0.5, min(new_scale, 5.0))

        if new_scale != canvas2_scale:
            canvas2_scale = new_scale
            width = int(cropped_image.width * canvas2_scale)
            height = int(cropped_image.height * canvas2_scale)

            try:
                scaled_img = cropped_image.resize((width, height), Image.LANCZOS)
                canvas2.delete("all")
                canvas2.image = ImageTk.PhotoImage(scaled_img)
                canvas2.create_image(0, 0, anchor=tk.NW, image=canvas2.image)
                canvas2.config(scrollregion=canvas2.bbox(tk.ALL))
            except Exception as e:
                print(f"Ошибка масштабирования: {e}")
    except Exception as e:
        print(f"Ошибка в zoom_canvas2: {e}")

def update_coordinates(event):
    global x_start, y_start, x_end, y_end, coordinates_entry
    try:
        # Получаем текст из поля и разбиваем его на координаты
        coordinates = coordinates_entry.get().split(",")

        # Проверяем, что получено 4 значения
        if len(coordinates) == 4:
            x_start, y_start, x_end, y_end = map(int, coordinates)
            print(
                f"Обновленные координаты: x_start={x_start}, y_start={y_start}, x_end={x_end}, y_end={y_end}"
            )
            draw_selection()  # Предполагается, что функция draw_selection() используется для обновления графики
        else:
            print("Ошибка: Введите 4 координаты, разделенные запятыми")
    except ValueError:
        # Игнорируем ошибку, если ввод некорректен
        print("Ошибка: Неверный формат координат")


# Процедура записи параметров в файл .env
def save_env(x_start, y_start, x_end, y_end, regex_pattern):
    set_key(ENV_FILE, "x_start", str(x_start))
    set_key(ENV_FILE, "y_start", str(y_start))
    set_key(ENV_FILE, "x_end", str(x_end))
    set_key(ENV_FILE, "y_end", str(y_end))
    set_key(ENV_FILE, "regex_pattern", str(regex_pattern))
    # regex_pattern = regex_pattern_entry.get()  # Получение текущего шаблона


# Функция для чтения параметров из .env файла
def read_env():
    global x_start, y_start, x_end, y_end, regex_pattern, selected_areas

    load_dotenv(ENV_FILE)
    try:
        x_start = int(os.getenv("x_start", DEFAULT_COORDINATES2["x_start"]))
        y_start = int(os.getenv("y_start", DEFAULT_COORDINATES2["y_start"]))
        x_end = int(os.getenv("x_end", DEFAULT_COORDINATES2["x_end"]))
        y_end = int(os.getenv("y_end", DEFAULT_COORDINATES2["y_end"]))
        regex_pattern = os.getenv("regex_pattern", DEFAULT_COORDINATES2["regex_pattern"])

        # Обновляем selected_areas
        selected_areas = [(None, x_start, y_start, x_end, y_end)]

        # Обновляем поле ввода координат
        if 'coordinates_entry' in globals():
            coordinates_entry.delete(0, tk.END)
            coordinates_entry.insert(0, f"{x_start},{y_start},{x_end},{y_end}")

        print(f"Загружены координаты из .env: x={x_start}, y={y_start}, w={x_end - x_start}, h={y_end - y_start}")

    except Exception as e:
        print(f"[ERROR] Ошибка при загрузке координат из .env: {e}")
        # Устанавливаем значения по умолчанию
        x_start, y_start, x_end, y_end = (
            DEFAULT_COORDINATES2["x_start"],
            DEFAULT_COORDINATES2["y_start"],
            DEFAULT_COORDINATES2["x_end"],
            DEFAULT_COORDINATES2["y_end"]
        )
        selected_areas = [(None, x_start, y_start, x_end, y_end)]

# Обработчик выхода
def on_closing():
    global root, x_start, y_start, x_end, y_end, regex_pattern
    if root is not None:  # Проверяем, что окно еще существует
        save_env(x_start, y_start, x_end, y_end, regex_pattern)
        root.destroy()  # Закрыть главное окно


class TextRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        self.widget.insert(tk.END, text)
        self.widget.see(tk.END)  # Прокрутка текста вниз

    def flush(self):
        pass  # Для совместимости с sys.stdout


@safe_execute
def save_current_page():
    """Сохранение текущей страницы как изображения."""
    global current_page, pdf_path
    if not pdf_path:
        messagebox.showerror("Ошибка", "Не выбран PDF файл.")
        return

    try:
        with fitz.open(pdf_path) as pdf:
            if current_page < 0 or current_page >= pdf.page_count:
                messagebox.showerror("Ошибка", "Неверный номер страницы.")
                return

            page = pdf.load_page(current_page)
            pix = page.get_pixmap(dpi=200)
            page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            output_file_name = f"page_{current_page + 1}.jpg"
            page_image.save(output_file_name)
            messagebox.showinfo("Успех", f"Страница сохранена как {output_file_name}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении страницы: {e}", exc_info=True)



def create_interface():
    global root, entry_pdf_path, canvas, label_page_number, label_page_size, label_scale, coordinates_entry
    global canvas2, canvas2_scale, label_coordinates, text_output, regex_pattern_entry, recognition_mode
    global ocr_engine_var, table_frame, tree  # Добавляем tree в глобальные переменные
    global selected_areas
    global debug_mode

    # Создание интерфейса
    root = tk.Tk()
    root.title(f"Распознавание текста из PDF - Текущая версия программы: {__version__}")
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Устанавливаем размеры окна
    window_width = 1600
    window_height = 800
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Верхняя рамка
    frame_top = tk.Frame(root)
    frame_top.pack(pady=10, padx=10, fill="x")
    frame_top.columnconfigure(1, weight=1)

    # Создаем стиль для кнопок с фиксированной шириной
    button_style = {'width': 14, 'anchor': 'center'}

    btn_select_pdf = tk.Button(frame_top, text="Выбрать PDF", command=select_pdf, **button_style)
    btn_load_registry = tk.Button(frame_top, text="Выбрать реестр", command=load_registry, **button_style)

    # btn_select_pdf = tk.Button(frame_top, text="Выбрать PDF", command=select_pdf, width=14)
    # btn_load_registry = tk.Button(frame_top, text="Выбрать реестр", command=load_registry, width=14)
    entry_pdf_path = tk.Entry(frame_top, width=150)
    btn_recognize = tk.Button(frame_top, text="Запуск распознавания", command=start_recognition_thread)
    btn_match = tk.Button(frame_top, text="Сопоставить", command=match_with_expected)
    # btn_save = tk.Button(frame_top, text="Сохранить результаты", command=save_results)
    btn_save = tk.Button(frame_top, text="Сохранить результаты", command=lambda: save_results(btn_save))

    btn_select_pdf.grid(row=0, column=0, padx=5, pady=5)
    btn_load_registry.grid(row=0, column=1, padx=5, pady=5)
    entry_pdf_path.grid(row=0, column=2, padx=5, pady=5)
    btn_recognize.grid(row=0, column=3, padx=5, pady=5)
    btn_match.grid(row=0, column=4, padx=5, pady=5)
    btn_save.grid(row=0, column=5, padx=5, pady=5)



    # Главная рамка (все элементы в одной строке)
    frame_main = tk.Frame(root)
    frame_main.pack(pady=5, padx=10, fill="x")

    # ===== 1. Левый блок (навигация + чекбокс) =====
    frame_left = tk.Frame(frame_main)
    frame_left.pack(side=tk.LEFT, fill="x", expand=False)

    # Навигационные кнопки (одинаковой ширины)
    button_width = 15  # Ширина всех кнопок
    btn_prev = tk.Button(frame_left, text="← Назад", command=prev_page, width=button_width)
    btn_next = tk.Button(frame_left, text="Вперед →", command=next_page, width=button_width)
    btn_check = tk.Button(frame_left, text="Проверить лист", command=check_image, width=button_width)
    btn_save = tk.Button(frame_left, text="Сохранить лист", command=save_current_page, width=button_width)


    # Чекбоксы
    recognition_mode = tk.IntVar(value=0)
    adv_checkbutton = tk.Checkbutton(frame_left, text="Расш. режим", variable=recognition_mode)

    debug_mode = tk.BooleanVar(value=False)
    debug_checkbutton = tk.Checkbutton(frame_left, text="Debug", variable=debug_mode, command=update_debug_mode)

    # Упаковка левого блока
    btn_prev.pack(side=tk.LEFT, padx=2)
    btn_next.pack(side=tk.LEFT, padx=2)
    btn_check.pack(side=tk.LEFT, padx=2)
    btn_save.pack(side=tk.LEFT, padx=2)
    adv_checkbutton.pack(side=tk.LEFT, padx=2)
    debug_checkbutton.pack(side=tk.LEFT, padx=2)

    # Первый разделитель
    separator1 = ttk.Separator(frame_main, orient="vertical")
    separator1.pack(side=tk.LEFT, fill="y", padx=5)

    # ===== 2. Центральный блок (OCR) =====
    frame_center = tk.Frame(frame_main)
    frame_center.pack(side=tk.LEFT, fill="x", expand=True)

    # Контейнер для элементов OCR (чтобы разместить их в одну строку)
    ocr_container = tk.Frame(frame_center)
    ocr_container.pack(fill="x", expand=True)

    # Элементы OCR
    lbl_ocr = tk.Label(ocr_container, text="OCR движок:")
    ocr_engine_var = tk.StringVar(value="Tesseract")
    ocr_options = ["Tesseract", "EasyOCR", "PaddleOCR"]
    if EASYOCR_AVAILABLE: ocr_options.append("EasyOCR")
    if PADDLEOCR_AVAILABLE: ocr_options.append("PaddleOCR")
    ocr_menu = tk.OptionMenu(ocr_container, ocr_engine_var, *ocr_options)
    btn_init_ocr = tk.Button(ocr_container, text="Инициализировать", command=init_ocr_engine)

    # Упаковка элементов OCR рядом
    lbl_ocr.pack(side=tk.LEFT, padx=2)
    ocr_menu.pack(side=tk.LEFT, padx=2)
    btn_init_ocr.pack(side=tk.LEFT, padx=2)

    # Второй разделитель
    separator2 = ttk.Separator(frame_main, orient="vertical")
    separator2.pack(side=tk.LEFT, fill="y", padx=5)

    # ===== 3. Правый блок (шаблон + координаты) =====
    frame_right = tk.Frame(frame_main)
    frame_right.pack(side=tk.RIGHT, fill="x", expand=False)

    # Элементы ввода (расширенные поля)
    lbl_pattern = tk.Label(frame_right, text="Шаблон:")
    regex_pattern_entry = tk.Entry(frame_right, width=25)  # Увеличенная ширина
    coordinates_entry = tk.Entry(frame_right, width=20)  # Увеличенная ширина

    # Упаковка правого блока
    lbl_pattern.pack(side=tk.LEFT, padx=2)
    regex_pattern_entry.pack(side=tk.LEFT, padx=2)
    coordinates_entry.pack(side=tk.LEFT, padx=2)

    # Инициализация полей
    regex_pattern_entry.insert(0, regex_pattern)
    coordinates_entry.bind("<KeyRelease>", update_coordinates)



    # Создание холстов и таблицы
    frame_canvases = tk.Frame(root)
    frame_canvases.pack(pady=10, padx=10, fill="both", expand=True)

    canvas_width = 750 // 2
    canvas_height = 500

    # Левый холст (PDF)
    canvas = tk.Canvas(frame_canvases, width=canvas_width, height=canvas_height, bg="grey")
    canvas.pack(side=tk.LEFT, anchor=tk.N, padx=5, pady=10)

    # Правый холст (выделенная область)
    canvas2 = tk.Canvas(frame_canvases, width=canvas_width, height=canvas_height, bg="grey")
    canvas2.pack(side=tk.LEFT, anchor=tk.N, padx=5, pady=10)

    # Обёртка для таблицы Treeview
    table_frame = tk.Frame(frame_canvases)
    table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Создание Treeview с прокруткой
    tree_scroll = tk.Scrollbar(table_frame)
    tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    tree = ttk.Treeview(table_frame, yscrollcommand=tree_scroll.set, selectmode="browse")
    tree.pack(fill=tk.BOTH, expand=True)

    tree_scroll.config(command=tree.yview)

    # Настройка колонок
    tree["columns"] = ("number", "expected", "recognized", "match", "score")
    tree.column("#0", width=0, stretch=tk.NO)  # Скрытая колонка
    tree.column("number", width=50, anchor=tk.CENTER)
    tree.column("expected", width=150, anchor=tk.W)
    tree.column("recognized", width=150, anchor=tk.W)
    tree.column("match", width=150, anchor=tk.W)
    tree.column("score", width=100, anchor=tk.CENTER)

    # Заголовки
    tree.heading("number", text="№")
    tree.heading("expected", text="Контейнер из XLS")
    tree.heading("recognized", text="Контейнер распознанный")
    tree.heading("match", text="Совпадение")
    tree.heading("score", text="Коэффициент")

    # Привязка события двойного клика для перехода к странице
    # tree.bind("<Double-1>", lambda e: on_tree_double_click())
    # tree.bind("<Double-1>", on_cell_double_click)
    # tree.bind("<Button-1>", on_tree_click)
    tree.bind("<Button-1>", on_tree_click)

    # Настройка обработчиков событий для холстов
    canvas.bind("<Button-1>", define_coordinates)
    canvas.bind("<B1-Motion>", draw_rectangle)
    canvas.bind("<ButtonRelease-1>", finish_coordinates)
    canvas.bind("<MouseWheel>", zoom_canvas)
    canvas2.bind("<MouseWheel>", zoom_canvas2)

    # Текстовое поле вывода
    text_output = scrolledtext.ScrolledText(root, width=100, height=10)
    text_output.pack(side=tk.BOTTOM, fill="x", pady=10, padx=10)
    text_output.config(state="normal")
    sys.stdout = TextRedirector(text_output)

    set_default_coordinates(coordinates_entry)



def update_debug_mode():
    """Обновляет режим отладки при изменении чекбокса"""
    global debug_mode
    print(f"Debug mode: {debug_mode.get()}")


def on_tree_click(event):
    """Обработчик кликов по Treeview"""
    global last_click_time

    # Определяем элемент, по которому кликнули
    region = tree.identify_region(event.x, event.y)
    if region != "cell":
        return

    current_time = event.time
    is_double_click = (current_time - last_click_time) < DOUBLE_CLICK_DELAY
    last_click_time = current_time

    item = tree.identify_row(event.y)
    column = tree.identify_column(event.x)

    # Всегда выполняем переход к странице
    goto_page(item)

    # Если это двойной клик - дополнительно открываем редактор
    if is_double_click and column == "#4":  # Только для столбца "Совпадение"
        edit_cell(item, column)

def goto_page(item):
    """Переход к указанной странице"""
    global current_page
    values = tree.item(item, 'values')
    if values and values[0]:  # values[0] - номер страницы
        try:
            current_page = int(values[0]) - 1
            load_page()
        except ValueError:
            pass

def edit_cell(item, column):
    """Редактирование ячейки"""
    x, y, width, height = tree.bbox(item, "#4")
    current_value = tree.item(item, "values")[3]  # Столбец "Совпадение"

    # Создаем поле для редактирования
    entry_edit = tk.Entry(tree, borderwidth=0, font=('Arial', 10))
    entry_edit.place(x=x, y=y, width=width, height=height, anchor=tk.NW)
    entry_edit.insert(0, current_value)
    entry_edit.select_range(0, tk.END)
    entry_edit.focus_set()

    def save_edit(event=None):
        """Сохранение отредактированного значения"""
        new_value = entry_edit.get()
        values = list(tree.item(item, "values"))
        values[3] = new_value

        # Пересчитываем коэффициент
        recognized = values[2] if len(values) > 2 else ""
        if recognized and new_value:
            score = is_similar_ratio(recognized, new_value)
            values[4] = f"{score:.2f}"
            update_row_color(item, score)

        tree.item(item, values=values)
        entry_edit.destroy()

    entry_edit.bind("<Return>", save_edit)
    entry_edit.bind("<FocusOut>", save_edit)

def update_row_color(item, score):
    """Обновление цвета строки"""
    if score == 1.0:
        tree.tag_configure("exact", background="#a8e6a8")
        tree.item(item, tags=("exact",))
    elif score >= 0.7:
        tree.tag_configure("partial", background="#fff8a8")
        tree.item(item, tags=("partial",))
    else:
        tree.tag_configure("none", background="#ffaaaa")
        tree.item(item, tags=("none",))


# def update_scroll_region(event=None):
#     table_canvas.configure(scrollregion=table_canvas.bbox("all"))

def load_registry():
    global table_entries, tree

    file_path = filedialog.askopenfilename(filetypes=[("Excel or CSV", "*.xlsx *.csv")])
    if not file_path:
        return

    container_data = []

    try:
        if file_path.endswith(".xlsx"):
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet = wb.active
            for row in sheet.iter_rows(min_row=5):  # начиная с 5-й строки
                cell = row[3].value  # Столбец D (индекс 3)
                if cell and isinstance(cell, str) and "/" in cell:
                    container_number = cell.split("/")[-1].strip()
                    container_data.append(container_number)

        elif file_path.endswith(".csv"):
            with open(file_path, encoding='utf-8') as f:
                reader = csv.reader(f)
                for idx, row in enumerate(reader):
                    if idx < 3:
                        continue
                    if len(row) >= 4 and "/" in row[3]:
                        container_number = row[3].split("/")[-1].strip()
                        container_data.append(container_number)

        else:
            messagebox.showerror("Ошибка", "Неподдерживаемый формат файла")
            return

        # Обновляем только столбец "Контейнер из XLS" для существующих строк
        for i, code in enumerate(container_data):
            if i < len(table_entries):
                # Обновляем данные в table_entries
                table_entries[i]["code"] = code

                # Получаем текущие значения строки
                current_values = list(tree.item(table_entries[i]["item_id"], 'values'))
                # Обновляем только второй столбец (индекс 1)
                current_values[1] = code
                # Устанавливаем обновленные значения
                tree.item(table_entries[i]["item_id"], values=current_values)

        messagebox.showinfo("Успех", f"Загружено {len(container_data)} контейнеров")

    except Exception as e:
        logging.error(f"Ошибка при загрузке реестра: {e}", exc_info=True)
        messagebox.showerror("Ошибка", f"Не удалось загрузить реестр: {e}")


def init_ocr_engine():
    global ocr_reader, EASYOCR_AVAILABLE, PADDLEOCR_AVAILABLE
    selected_engine = ocr_engine_var.get()

    try:
        if selected_engine == "EasyOCR":
            import easyocr
            ocr_reader = easyocr.Reader(['en'])  # Загрузка моделей
            EASYOCR_AVAILABLE = True
            messagebox.showinfo("Успех", "EasyOCR инициализирован!")

        elif selected_engine == "PaddleOCR":
            import paddle  # noqa
            from paddleocr import PaddleOCR
            ocr_reader = PaddleOCR(use_angle_cls=True, lang='en')
            PADDLEOCR_AVAILABLE = True
            messagebox.showinfo("Успех", "PaddleOCR инициализирован!")
        else:
            ocr_reader = None
            messagebox.showinfo("Инфо", "Используется Tesseract")

    except ImportError as e:
        error_msg = {
            "EasyOCR": "pip install easyocr",
            "PaddleOCR": "pip install paddlepaddle paddleocr"
        }.get(selected_engine, f"pip install {selected_engine.lower()}")
        logging.error("Ошибка", f"Не хватает зависимостей!\nУстановите:\n{error_msg}")
    except Exception as e:
        logging.error("Ошибка", f"Не удалось инициализировать {selected_engine}: {str(e)}")
        ocr_reader = None


def update_table(data, tree_widget):
    """Обновление таблицы Treeview"""
    global tree, table_entries, expected_containers

    # Очищаем таблицу
    for item in tree_widget.get_children():
        tree_widget.delete(item)

    table_entries = []
    expected_containers = [code for _, code in data]

    for number, code in data:
        # Добавляем строку в Treeview
        item_id = tree_widget.insert("", tk.END, values=(number, code, "", "", ""))

        # Сохраняем данные для дальнейшего использования
        entry = {
            "index": number,
            "code": code,
            "recognized": "",
            "item_id": item_id  # Сохраняем ID элемента Treeview
        }
        table_entries.append(entry)


def on_match_edit(row_index):
    """Обработчик редактирования поля совпадения"""
    global table_entries
    if 0 <= row_index < len(table_entries):
        new_value = table_entries[row_index]["match_var"].get()
        # Здесь можно добавить логику обработки изменений
        print(f"Изменено совпадение для строки {row_index + 1}: {new_value}")
        # Обновляем расчет коэффициента
        update_score(row_index)


def update_score(row_index):
    """Обновляет коэффициент совпадения"""
    global table_entries
    entry = table_entries[row_index]
    recognized = entry["recognized"]
    match = entry["match_var"].get()

    if recognized and match:
        score = is_similar_ratio(recognized, match)
        entry["label_score"].config(text=f"{score:.2f}")
        # Изменяем цвет в зависимости от результата
        bg_color = "lightgreen" if score >= 0.9 else "khaki" if score >= 0.7 else "tomato"
        entry["label_score"].config(bg=bg_color)


# Функция для проверки обновлений
def check_for_updates():
    threading.Thread(target=_check_updates, daemon=True).start()

def _check_updates():
    try:
        # URL для получения информации о релизах
        repo_url = "https://api.github.com/repos/vanitoo/pythonProject-OpenCV-PDF-Build/releases/latest"
        response = requests.get(repo_url, timeout=5)

        response = requests.get(repo_url)
        if response.status_code == 200:
            latest_release = response.json()
            latest_version = latest_release["tag_name"].lstrip("v")  # Убираем префикс 'v'
            download_url = latest_release["assets"][0]["browser_download_url"]

            # Сравниваем текущую версию с последней на GitHub
            if compare_versions(__version__, latest_version):
                text_output.delete(1.0, tk.END)
                text_output.insert(
                    tk.END,
                    f"Появилась новая версия {latest_version}, рекомендуется обновиться\n",
                )
                text_output.insert(tk.END, download_url)
            else:
                text_output.delete(1.0, tk.END)
                text_output.insert(tk.END, "У вас последняя версия.")
    except Exception:
        pass  # Не блокировать интерфейс при ошибках


# Функция для сравнения версий
def compare_versions(current_version: str, latest_version: str) -> bool:
    try:
        current = tuple(map(int, current_version.split(".")))
        latest = tuple(map(int, latest_version.split(".")))
    except ValueError:
        raise ValueError("Version numbers must contain only integers separated by dots")

    # Compare component by component
    for current_part, latest_part in zip(current, latest):
        if current_part < latest_part:
            return True
        if current_part > latest_part:
            return False

    return len(current) < len(latest)


def check_dependencies():
    missing = []
    if not EASYOCR_AVAILABLE:
        missing.append("easyocr (pip install easyocr)")
    if not PADDLEOCR_AVAILABLE:
        missing.append("paddleocr (pip install paddleocr paddlepaddle)")

    if missing:
        messagebox.showwarning(
            "Предупреждение",
            f"Следующие OCR-движки недоступны:\n{', '.join(missing)}\n\n"
            "Вы можете установить их командой:\npip install easyocr paddleocr paddlepaddle"
        )


def main():
    """Основная функция для запуска приложения."""
    try:
        # check_dependencies()
        set_tesseract_path()
        read_env()
        create_interface()  # Вызов функции для создания интерфейса
        check_for_updates()
        root.mainloop()  # Запуск цикла обработки событий
    except KeyboardInterrupt:
        print("Программа завершена пользователем.")
        root.quit()  # Завершаем работу Tkinter, если прервано вручную


# Запуск программы
if __name__ == "__main__":
    main()
    # cProfile.run('main()', 'output.prof')  # Запуск профилирования


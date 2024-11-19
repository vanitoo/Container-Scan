import sys
import logging
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import cv2
import fitz  # PyMuPDF
import numpy as np
import pytesseract
from PIL import Image, ImageTk
from dotenv import load_dotenv, set_key


# Глобальные переменные (лучше использовать класс для состояния)
DEFAULT_COORDINATES2 = {
    'x_start': 27,
    'y_start': 297,
    'x_end': 81,
    'y_end': 318,
    'regex_pattern': '^[A-Z]{3}U\d{7}$'
}
#x_start, y_start, x_end, y_end = None, None, None, None
current_page = 0
pdf_path = None
pdf = None
image_display = None
rect_id = None
scale_percent = 100  # Масштаб для обработки координат
ENV_FILE = '.env'
text_output = None
reader = None



# Настройка логирования
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
        r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe',
        r'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe',
        os.path.expanduser(r'~\\Tesseract-OCR\\tesseract.exe'),
        os.path.expanduser(r'~\\AppData\\Local\\Tesseract-OCR\\tesseract.exe'),
        os.path.expanduser(r'~\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe')]
        # Проверка пути в папке Programs

    # Проверка всех возможных путей
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            #print(f"Путь для Tesseract установлен: {path}")
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
    global rect_id, x_start, y_start, x_end, y_end, canvas2, cropped_image

    # Удаляем предыдущий прямоугольник, если он был нарисован
    if rect_id:
        canvas.delete(rect_id)
    rect_id = canvas.create_rectangle(x_start, y_start, x_end, y_end, outline="red", width=2)

    canvas.coords(rect_id, x_start, y_start, x_end, y_end)
    update_coordinates_entry()

    # Вырез области изображения по координатам
    if page_image:
        # Вырезка области из оригинального изображения
        cropped_image = page_image.crop((x_start, y_start, x_end, y_end))
        # Отображение на втором холсте
        cropped_image_display = ImageTk.PhotoImage(image=cropped_image)
        canvas2.create_image(0, 0, anchor=tk.NW, image=cropped_image_display)
        # Обновление ссылки для предотвращения сборки мусора
        canvas2.image = cropped_image_display

# Функция для выбора файла PDF
def select_pdf():
    global pdf_path, current_page, pdf, entry_pdf_path
    pdf_path = filedialog.askopenfilename(filetypes=[("PDF файлы", "*.pdf")])
    if pdf_path:
        entry_pdf_path.delete(0, tk.END)
        entry_pdf_path.insert(0, pdf_path)
        current_page = 0
        load_page()


    #try:
    #    pdf_path = filedialog.askopenfilename(filetypes=[("PDF файлы", "*.pdf")])
    #    if pdf_path:
    #        entry_pdf_path.delete(0, tk.END)
    #        entry_pdf_path.insert(0, pdf_path)
    #        current_page = 0
    #        load_page()
    #except Exception as e:
    #    messagebox.showerror("Ошибка", f"Не удалось выбрать или загрузить PDF: {e}")

# Функция загрузки и отображения страницы PDF
@safe_execute
def load_page():
    global image_display, pdf, current_page, page_image, scale_factor, page_width2, page_height2, canvas, label_page_number, label_page_size, label_scale, total_pages
    if not pdf_path:
        return
    try:
        with fitz.open(pdf_path) as pdf:
            current_page = max(0, min(current_page, pdf.page_count - 1))
            page = pdf.load_page(current_page)
            total_pages = pdf.page_count
            pix = page.get_pixmap(dpi=150)

            Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


            page_width2, page_height2 = page.rect.width, page.rect.height
            print(f"Страница {current_page + 1}: размер {page_width2} x {page_height2} points")


            ## Преобразование Pixmap в объект PIL Image
            page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            # Получаем размеры canvas и изображения
            #canvas_width = canvas.winfo_width()
            #canvas_height = canvas.winfo_height()
            #img_width, img_height = img.size
            # Рассчитываем коэффициент масштабирования, чтобы изображение вписалось в canvas
            #scale = min(canvas_width / img_width, canvas_height / img_height)
            #print(scale)
            #new_width = int(img_width * scale)
            #new_height = int(img_height * scale)
            #print(new_width,new_height)
            # Масштабируем изображение
            #img_resized = img.resize((new_width, new_height), Image.LANCZOS)
            # Преобразуем изображение в формат, совместимый с tkinter
            #img_tk = ImageTk.PhotoImage(img_resized)
            # Очищаем canvas и добавляем новое изображение
            #canvas.delete("all")
            #canvas.create_image((canvas_width - new_width) // 2, (canvas_height - new_height) // 2, anchor="nw",image=img_tk)
            # Сохраняем ссылку на изображение, чтобы избежать его удаления сборщиком мусора
            #canvas.image = img_tk




            # Получение размеров холста
            canvas_height = canvas.winfo_height()
            image_height = page_image.height

            # Вычисление коэффициента масштабирования для подгонки по высоте с учетом scale_percent
            scale_factor = (scale_percent / 100) * (canvas_height / image_height)

            # Масштабирование изображения с учетом scale_percent
            scaled_width = int(page_image.width * scale_factor)
            scaled_height = int(page_image.height * scale_factor)
            page_image = page_image.resize((scaled_width, scaled_height), Image.LANCZOS)

            # Отображение изображения на холсте
            image_display = ImageTk.PhotoImage(image=page_image)
            if canvas:
                canvas.create_image(0, 0, anchor=tk.NW, image=image_display)
                canvas.config(scrollregion=canvas.bbox(tk.ALL))

            # Обновление информации о текущей странице
            #label_page_number.config(text=f"Страница: {current_page + 1}/{pdf.page_count}")
            root.title(
                f"Распознавание текста из PDF - Страница {current_page + 1}/{pdf.page_count} - Координаты: ")

            # Обновление информации о размере страницы (Page Size)
            page_size_text = f"{pix.width}x{pix.height}"  # Размеры страницы в пикселях
            #label_page_size.config(text=f"Page Size: {page_size_text}")
            print(f"Page Size: {page_size_text}")

            # Обновление масштаба (Scale)
            scale_text = f"{round(scale_factor * 100)}%"  # Масштаб в процентах, округленный до целых
            #label_scale.config(text=f"Scale: {scale_text}")
            print("Scale:", scale_text)

            draw_selection()
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось загрузить страницу: {e}")

# Функция для выбора координат области
def define_coordinates(event):
    global x_start, y_start, rect_id, scale_percent, scale_factor
    # Координаты события с учетом масштаба
    x_start = int(event.x)
    y_start = int(event.y)
    print(scale_factor)
    print(scale_percent)
    print(event.x,event.y)
    print(x_start, y_start)

    # Удаляем старое выделение, если оно есть
    if rect_id:
        canvas.delete(rect_id)

    # Создаем новый прямоугольник, начальная точка
    rect_id = canvas.create_rectangle(x_start, y_start, x_start, y_start, outline="red", width=2)
    update_coordinates_entry()

def draw_rectangle(event):
    global rect_id, x_start, y_start
    x_end, y_end = event.x, event.y
    if rect_id is not None:
        canvas.coords(rect_id, x_start, y_start, x_end, y_end)

def finish_coordinates(event):
    global x_start, y_start, x_end, y_end, cropped_image_display, cropped_image, canvas2, label_coordinates, total_pages
    x_end, y_end = event.x, event.y

#    label_coordinates.configure(text=f"Координаты: ({x_start}, {y_start}) -> ({x_end}, {y_end})")

    root.title(
        f"Распознавание текста из PDF - Страница {current_page + 1}/{total_pages} - Координаты: ({x_start}, {y_start}) -> ({x_end}, {y_end})"
    )

    canvas.coords(rect_id, x_start, y_start, x_end, y_end)
    update_coordinates_entry()

    # Вырез области изображения по координатам
    if page_image:
        # Вырезка области из оригинального изображения
        cropped_image = page_image.crop((x_start, y_start, x_end, y_end))

        # Отображение на втором холсте
        cropped_image_display = ImageTk.PhotoImage(image=cropped_image)
        canvas2.create_image(0, 0, anchor=tk.NW, image=cropped_image_display)

        # Обновление ссылки для предотвращения сборки мусора
        canvas2.image = cropped_image_display

# Функция обновления метки координат
def update_coordinates_label():
    global x_start, y_start, x_end, y_end, label_coordinates
    if x_start is not None and y_start is not None and x_end is not None and y_end is not None:
        label_coordinates.config(
            text=f"Координаты: x={x_start}, y={y_start}, width={x_end - x_start}, height={y_end - y_start}")

def update_coordinates_entry():
    global x_start, y_start, x_end, y_end, coordinates_entry
    if x_start is not None and y_start is not None and x_end is not None and y_end is not None:
        coordinates_text = f"{x_start},{y_start},{x_end},{y_end}"
        coordinates_entry.delete(0, tk.END)
        coordinates_entry.insert(0, coordinates_text)

@safe_execute
def format_extracted_text2(text, i):
    global regex_pattern, regex_pattern_entry
    regex_pattern = regex_pattern_entry.get()  # Получение шаблона из поля ввода
    cleaned_text = re.sub(r'[^A-Za-z0-9]', '', text).upper()
    if re.match(regex_pattern, cleaned_text):
        return cleaned_text

    # Ваш существующий код для обработки текста...

# Функция для проверки и форматирования распознанного текста
def format_extracted_text(text, i):

    # Удаление всех символов, кроме английских букв и цифр
    cleaned_text = re.sub(r'[^A-Za-z0-9]', '', text).upper()

    # Проверка формата: 4 буквы (в верхнем регистре) + 7 цифр
    if re.match(r'^[A-Z]{4}\d{7}$', cleaned_text):
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
    formatted_text = formatted_text[:11]  # Убедиться, что длина не превышает 11 символов

    # Дополнение '@', если строка короче
    while len(formatted_text) < 11:
        formatted_text += "@"

    return formatted_text

# Функция для выполнения длительной задачи в потоке
def start_recognition_thread():
    threading.Thread(target=start_recognition, daemon=True).start()
#    start_task_with_progress(start_recognition)

@safe_execute
def start_recognition():
    global pdf_path, x_start, y_start, x_end, y_end, canvas2, cropped_image

    if not pdf_path:
        messagebox.showerror("Ошибка", "Пожалуйста, выберите PDF файл.")
        return

    # Проверка наличия значений координат
    if x_start is None or y_start is None or x_end is None or y_end is None:
        messagebox.showerror("Ошибка", "Координаты не заданы.")
        return

    print(f"Используемые координаты: x_start={x_start}, y_start={y_start}, x_end={x_end}, y_end={y_end}")

    # Создание выходной папки
    output_dir = create_output_directory(pdf_path)

    with fitz.open(pdf_path) as pdf:
        total_pages = pdf.page_count
        print(f"Количество страниц в PDF: {total_pages}")

        for i in range(total_pages):  # Используем индекс для загрузки страниц
            page = pdf.load_page(i)  # Загружаем страницу по индексу
            pix = page.get_pixmap(dpi=150)
            page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Проверка координат на допустимость
            if x_start < 0 or y_start < 0 or x_end > page_image.width or y_end > page_image.height:
                messagebox.showerror("Ошибка", f"Координаты выходят за пределы страницы {i + 1}.")
                continue

            #canvas.coords(rect_id, x_start, y_start, x_end, y_end)
            #update_coordinates_entry()

            # Обратный коэффициент масштабирования
            inverse_scale_factor = 1 / scale_factor
            # Преобразование координат для использования с оригинальным изображением
            x_start_orig = int(x_start * inverse_scale_factor)
            y_start_orig = int(y_start * inverse_scale_factor)
            x_end_orig = int(x_end * inverse_scale_factor)
            y_end_orig = int(y_end * inverse_scale_factor)


            cropped_image = page_image.crop((x_start_orig, y_start_orig, x_end_orig, y_end_orig))
            #cropped_image = page_image.crop((x_start, y_start, x_end, y_end))

            cropped_image_display = ImageTk.PhotoImage(image=cropped_image)
            canvas2.create_image(0, 0, anchor=tk.NW, image=cropped_image_display)
            canvas2.image = cropped_image_display

            # Преобразование изображения для распознавания текста
            open_cv_image = np.array(cropped_image)
            open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)

            extracted_text = pytesseract.image_to_string(open_cv_image, lang='eng').strip()

            # Форматирование распознанного текста
            formatted_text = format_extracted_text(extracted_text, i + 1)


            # Печать распознанного текста
            print(f"Страница {i + 1}:")
            print(f"Распознанный текст: {formatted_text}")

            # Сохранение распознанного текста в файл
            with open(os.path.join(output_dir, f"{i + 1}_text.txt"), "w", encoding="utf-8") as f:
                f.write(extracted_text)

            # Сохранение области для сверки
            cv_output_file_name = os.path.join(output_dir, f"{i + 1}_cv.jpg")
            pil_image = Image.fromarray(cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2RGB))
            pil_image.save(cv_output_file_name)
            print(f"Сохранена область для сверки: {cv_output_file_name}")

            # Сохранение страницы
            output_file_name = os.path.join(output_dir, f"{i + 1}_{formatted_text}.jpg")
            page_image.save(output_file_name)
            print(f"Страница сохранена как: {output_file_name}")

def enhanced_recognition11(image):
    """Функция для расширенного распознавания текста с дополнительной обработкой."""
    # Применение фильтров и предобработки для улучшения качества изображения
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Применение шумоподавления
    processed_image = cv2.medianBlur(thresh, 3)
    # Увеличение разрешения
    processed_image = cv2.resize(processed_image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # Распознавание текста
    extracted_text = pytesseract.image_to_string(processed_image, lang='eng', config='--oem 1 --psm 6').strip()

    return extracted_text

def enhanced_recognition12(image):
    """Расширенное распознавание с применением нескольких методов обработки."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_image = clahe.apply(thresh)

    # Увеличение разрешения
    enhanced_image = cv2.resize(enhanced_image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    extracted_text = pytesseract.image_to_string(enhanced_image, lang='eng', config='--oem 1 --psm 6').strip()
    return extracted_text

def run_ocr_in_thread(image, **kwargs):
    """Запуск OCR в отдельном потоке с передачей параметров."""
    threading.Thread(target=enhanced_recognition, args=(image,), kwargs=kwargs).start()

@safe_execute
def enhanced_recognition(image, use_grayscale=True, use_median_blur=True, use_thresholding=True,
                         use_clahe=True, use_resize=True, use_deskew=True, use_noise_removal=True,
                         use_morphological_ops=True, use_channel_extraction=False, channel='blue'):
    """Расширенная функция распознавания текста с поддержкой EasyOCR и настройками включения этапов обработки."""

    # Преобразование в оттенки серого
    if use_grayscale:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

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
        image = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

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
        if channel == 'blue':
            image = image[:, :, 0]
        elif channel == 'green':
            image = image[:, :, 1]
        elif channel == 'red':
            image = image[:, :, 2]

    extracted_text = pytesseract.image_to_string(image, lang='eng').strip()

    return extracted_text

def check_image():
    global x_start, y_start, x_end, y_end, current_page, pdf_path, canvas2, text_output, recognition_mode

    # Проверка на наличие пути к PDF
    if not pdf_path:
        messagebox.showerror("Ошибка", "Не выбран PDF файл.")
        return

    # Проверка координат
    if None in (x_start, y_start, x_end, y_end):
        messagebox.showwarning("Внимание", "Пожалуйста, выделите область для анализа.")
        return

    try:
        # Открытие PDF файла
        with fitz.open(pdf_path) as pdf:
            if current_page < 0 or current_page >= pdf.page_count:
                messagebox.showerror("Ошибка", "Неверный номер страницы.")
                return

            # Загрузка текущей страницы
            page = pdf.load_page(current_page)
            pix = page.get_pixmap(dpi=150)
            page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Обратный коэффициент масштабирования
            inverse_scale_factor = 1 / scale_factor
            # Преобразование координат для использования с оригинальным изображением
            x_start_orig = int(x_start * inverse_scale_factor)
            y_start_orig = int(y_start * inverse_scale_factor)
            x_end_orig = int(x_end * inverse_scale_factor)
            y_end_orig = int(y_end * inverse_scale_factor)

            # Обрезка изображения по выбранной области
            cropped_image = page_image.crop((x_start_orig, y_start_orig, x_end_orig, y_end_orig))

            # Отображение обрезанного изображения на холсте canvas2 (если необходимо)
            cropped_image_display = ImageTk.PhotoImage(image=cropped_image)
            canvas2.create_image(0, 0, anchor=tk.NW, image=cropped_image_display)
            canvas2.image = cropped_image_display

            # Преобразование изображения для распознавания текста
            open_cv_image = np.array(cropped_image)
            open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)


            if recognition_mode.get() == 0:
                # Обычное распознавание
                extracted_text = pytesseract.image_to_string(open_cv_image, lang='eng').strip()
            else:
                # Расширенное распознавание
                extracted_text = enhanced_recognition11(open_cv_image)
                #extracted_text = enhanced_recognition(open_cv_image, use_grayscale=False, use_median_blur=False, use_thresholding=False,
                #                        use_clahe=False, use_resize=False, use_deskew=False, use_noise_removal=False,
                #                        use_morphological_ops=False, use_channel_extraction=False)

            #            formatted_text = format_extracted_text(extracted_text, i + 1)
#            print(f"Страница {i + 1}: {formatted_text}")


            # Форматирование распознанного текста
            formatted_text = format_extracted_text(extracted_text, current_page + 1)
            print(f"Страница {current_page + 1}: {formatted_text}")
            print("Распознанное имя:",formatted_text)


            # Вывод распознанного текста в консоль
            print("Распознанный текст:")
            print(extracted_text)

            state = "включен" if recognition_mode.get() == 1 else "выключен"
            print(f"Расширенный режим распознавания {state}")

            # Обновление текстового поля (если используется)
            #text_output.delete(1.0, "end")
            #text_output.insert("end", extracted_text)


    except Exception as e:
        logging.error(f"Ошибка при распознавании: {e}", exc_info=True)
        messagebox.showerror("Ошибка", f"Ошибка при распознавании: {e}")

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
def zoom_in():
    global scale_percent
    scale_percent += 10  # Увеличиваем на 10%
    load_page()  # Перезагружаем страницу с новым масштабом

# Функция уменьшения масштаба
def zoom_out():
    global scale_percent
    if scale_percent > 10:  # Уменьшаем на 10% минимум
        scale_percent -= 10
        load_page()  # Перезагружаем страницу с новым масштабом

# Функция для обновления поля с дефолтными координатами
def set_default_coordinates(coordinates_entry):
    coordinates_text = f"{DEFAULT_COORDINATES2['x_start']},{DEFAULT_COORDINATES2['y_start']},{DEFAULT_COORDINATES2['x_end']},{DEFAULT_COORDINATES2['y_end']}"
    #coordinates_text = f"{DEFAULT_COORDINATES[0]},{DEFAULT_COORDINATES[1]},{DEFAULT_COORDINATES[2]},{DEFAULT_COORDINATES[3]}"
    coordinates_entry.delete(0, tk.END)
    coordinates_entry.insert(0, coordinates_text)

# Функция для проверки формата координат
def validate_coordinates_format(coordinates_text):
    parts = coordinates_text.split(',')
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        return True
    return False

def zoom_canvas(event):
    global canvas_scale, cropped_image, cropped_image_display, page_image
    zoom_factor = 1.1 if event.delta > 0 else 0.9  # Увеличение или уменьшение масштаба
    canvas_scale *= zoom_factor

    if page_image:  # Проверка, что оригинальное обрезанное изображение существует
        # Масштабирование изображения
        new_width = int(page_image.width * canvas_scale)
        new_height = int(page_image.height * canvas_scale)
        scaled_image = page_image.resize((new_width, new_height), Image.LANCZOS)

        # Обновление отображаемого изображения
        cropped_image_display = ImageTk.PhotoImage(image=scaled_image)
        canvas.create_image(0, 0, anchor=tk.NW, image=cropped_image_display)
        canvas.image = cropped_image_display  # Сохранение ссылки для предотвращения сборки мусора

def zoom_canvas2(event):
    global canvas2_scale, cropped_image, cropped_image_display, page_image, canvas2, canvas2_scale
    zoom_factor = 1.1 if event.delta > 0 else 0.9  # Увеличение или уменьшение масштаба
    canvas2_scale *= zoom_factor

    if cropped_image:  # Проверка, что оригинальное обрезанное изображение существует
        # Масштабирование изображения
        new_width = int(cropped_image.width * canvas2_scale)
        new_height = int(cropped_image.height * canvas2_scale)
        scaled_image = cropped_image.resize((new_width, new_height), Image.LANCZOS)

        # Обновление отображаемого изображения
        cropped_image_display = ImageTk.PhotoImage(image=scaled_image)
        canvas2.create_image(0, 0, anchor=tk.NW, image=cropped_image_display)
        canvas2.image = cropped_image_display  # Сохранение ссылки для предотвращения сборки мусора

def update_coordinates(event):
    global x_start, y_start, x_end, y_end, coordinates_entry
    try:
        # Получаем текст из поля и разбиваем его на координаты
        coordinates = coordinates_entry.get().split(',')

        # Проверяем, что получено 4 значения
        if len(coordinates) == 4:
            x_start, y_start, x_end, y_end = map(int, coordinates)
            print(f"Обновленные координаты: x_start={x_start}, y_start={y_start}, x_end={x_end}, y_end={y_end}")
            draw_selection()  # Предполагается, что функция draw_selection() используется для обновления графики
        else:
            print("Ошибка: Введите 4 координаты, разделенные запятыми")
    except ValueError:
        # Игнорируем ошибку, если ввод некорректен
        print("Ошибка: Неверный формат координат")

# Процедура записи параметров в файл .env
def save_env(x_start, y_start, x_end, y_end, regex_pattern):
    set_key(ENV_FILE, 'x_start', str(x_start))
    set_key(ENV_FILE, 'y_start', str(y_start))
    set_key(ENV_FILE, 'x_end', str(x_end))
    set_key(ENV_FILE, 'y_end', str(y_end))
    set_key(ENV_FILE, 'regex_pattern', str(regex_pattern))
    #regex_pattern = regex_pattern_entry.get()  # Получение текущего шаблона

# Функция для чтения параметров из .env файла
def read_env() -> object:
    global x_start, y_start, x_end, y_end, regex_pattern, regex_pattern_entry
    load_dotenv(ENV_FILE)
    # Загрузка значений из .env в одноименные переменные
    x_start = int(os.getenv('x_start', DEFAULT_COORDINATES2['x_start']))
    y_start = int(os.getenv('y_start', DEFAULT_COORDINATES2['y_start']))
    x_end = int(os.getenv('x_end', DEFAULT_COORDINATES2['x_end']))
    y_end = int(os.getenv('y_end', DEFAULT_COORDINATES2['y_end']))
    regex_pattern = (os.getenv('regex_pattern', DEFAULT_COORDINATES2['regex_pattern']))
    #regex_pattern_entry.insert(0, regex_pattern)  # Пример шаблона
    print(x_start, y_start, x_end, y_end)

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
            pix = page.get_pixmap(dpi=150)
            page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            output_file_name = f"page_{current_page + 1}.jpg"
            page_image.save(output_file_name)
            messagebox.showinfo("Успех", f"Страница сохранена как {output_file_name}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении страницы: {e}", exc_info=True)



def create_interface():
    global root, entry_pdf_path, canvas, label_page_number, label_page_size, label_scale, coordinates_entry
    global canvas2, canvas2_scale, label_coordinates, text_output, regex_pattern_entry, recognition_mode

    # Создание интерфейса
    root = tk.Tk()
    root.title("Распознавание текста из PDF")
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Устанавливаем размеры окна (например, 400x300)
    window_width = 800
    window_height = 800
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    root.geometry(f'{window_width}x{window_height}+{x}+{y}')


    #################################################################

    # Верхняя рамка
    frame_top = tk.Frame(root)
    frame_top.pack(pady=10, padx=10, fill="x")
    # Настройка столбцов для растягивания
    frame_top.columnconfigure(0, weight=1)
    frame_top.columnconfigure(1, weight=3)
    frame_top.columnconfigure(2, weight=1)
    # Группировка элементов в верхней рамке
    elements_top = [
        (tk.Button(frame_top, text="Выбрать PDF", command=select_pdf), 0, 0),
        (tk.Entry(frame_top, width=50), 0, 1),
        (tk.Button(frame_top, text="Запуск распознавания", command=start_recognition_thread), 0, 2)
    ]
    for element, row, col in elements_top:
        element.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
    entry_pdf_path = elements_top[1][0]  # Привязка поля ввода для глобального использования


    #################################################################

    # Рамка для навигации
    frame_navigation = tk.Frame(root)
    frame_navigation.pack(pady=5, padx=10, fill="x")
    elements_navigation = [
        (tk.Button(frame_navigation, text="Предыдущая страница", command=prev_page), 0, 0),
        (tk.Button(frame_navigation, text="Следующая страница", command=next_page), 0, 1),
        (tk.Button(frame_navigation, text="-10%", command=zoom_out), 0, 2),
        (tk.Button(frame_navigation, text="+10%", command=zoom_in), 0, 3),
        (tk.Label(frame_navigation, text=" "), 0, 4),  # Разделитель между кнопками
        (tk.Button(frame_navigation, text="Проверить", command=check_image),0,5),
        (tk.Button(frame_navigation, text="Сохранить текущий лист", command=save_current_page),0,6),
    ]
    for element, row, col in elements_navigation:
        element.grid(row=row, column=col, padx=5, pady=5)

    # Переменная для хранения выбранного режима распознавания
    recognition_mode = tk.IntVar(value=0)

    # Создание и размещение Checkbutton отдельно
    adv_checkbutton = tk.Checkbutton(frame_navigation, text="Расш.Режим", variable=recognition_mode)
    adv_checkbutton.grid(row=0, column=7, padx=5, pady=5)

    # Настройка столбцов для растягивания
    frame_navigation.columnconfigure(1, weight=1)


    #################################################################

    # Рамка для ввода шаблона и координат
    frame_pattern = tk.Frame(root)
    frame_pattern.pack(pady=5, padx=10, fill="x")

    # Настройка столбцов для растягивания
    frame_pattern.columnconfigure(1, weight=1)

    # Группировка элементов в рамке
    elements_pattern = [
        (tk.Label(frame_pattern, text="Шаблон поиска2:"), 0, 0),
        (tk.Entry(frame_pattern, width=20), 0, 1),
        (tk.Entry(frame_pattern, width=20), 0, 2),
        (tk.Label(frame_pattern, text="Координаты: -"), 0, 3)
    ]

    for element, row, col in elements_pattern:
        element.grid(row=row, column=col, padx=5, pady=5, sticky="ew")

    # Инициализация элементов для дальнейшего использования
    regex_pattern_entry = elements_pattern[1][0]  # Поле для ввода шаблона
    coordinates_entry = elements_pattern[2][0]  # Поле для ввода координат

    # Вставка начального значения в поле ввода шаблона
    regex_pattern_entry.insert(0, regex_pattern)

    # Привязка события для поля координат
    coordinates_entry.bind("<KeyRelease>", update_coordinates)

    #################################################################

    # Создание холстов
    frame_canvases = tk.Frame(root)
    frame_canvases.pack(pady=10, padx=10, fill="both", expand=True)

    canvas_width = 750 // 2
    canvas_height = 500

    canvas = tk.Canvas(frame_canvases, width=canvas_width, height=canvas_height, bg="grey")
    canvas.pack(side=tk.LEFT, anchor=tk.N, padx=5, pady=10)

    canvas2 = tk.Canvas(frame_canvases, width=canvas_width, height=canvas_height, bg="grey")
    canvas2.pack(side=tk.LEFT, anchor=tk.N, padx=5, pady=10)

    canvas.bind("<Button-1>", define_coordinates)
    canvas.bind("<B1-Motion>", draw_rectangle)
    canvas.bind("<ButtonRelease-1>", finish_coordinates)

    # Масштаб
    canvas2_scale = 1.0

    canvas2.bind("<MouseWheel>", zoom_canvas2)

    text_output = scrolledtext.ScrolledText(root, width=100, height=10)
    text_output.pack(side=tk.BOTTOM, fill="x", pady=10, padx=10)
    text_output.config(state='normal')
    sys.stdout = TextRedirector(text_output)

    set_default_coordinates(coordinates_entry)



def main():
    """Основная функция для запуска приложения."""
    try:
        set_tesseract_path()
        read_env()
        create_interface()  # Вызов функции для создания интерфейса
        root.mainloop()  # Запуск цикла обработки событий
    except KeyboardInterrupt:
        print("Программа завершена пользователем.")
        root.quit()  # Завершаем работу Tkinter, если прервано вручную

# Запуск программы
if __name__ == "__main__":
    main()
    #cProfile.run('main()', 'output.prof')  # Запуск профилирования

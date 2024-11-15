import os
import sys
import pytesseract
from PIL import Image, ImageTk
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import re
import threading
import fitz
from dotenv import load_dotenv, set_key


# Глобальные переменные (лучше использовать класс для состояния)
DEFAULT_COORDINATES2 = {
    'x_start': 27,
    'y_start': 297,
    'x_end': 81,
    'y_end': 318
}
#x_start, y_start, x_end, y_end = None, None, None, None
current_page = 0
pdf_path = None
pdf = None
image_display = None
rect_id = None
scale_percent = 100  # Масштаб для обработки координат
ENV_FILE = '.env'
default_params = {'x1': 27,'y1': 297,'x2': 81,'y2': 318}


# Функция для проверки и создания .env файла с параметрами по умолчанию
def check_and_create_env():
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'w') as file:
            for key, value in DEFAULT_COORDINATES2.items():
                file.write(f'{key}={value}\n')


# Функция для чтения параметров из .env файла
def read_env() -> object:
    global x_start, y_start, x_end, y_end
    load_dotenv(ENV_FILE)
    # Загрузка значений из .env в одноименные переменные
    x_start = int(os.getenv('x_start', DEFAULT_COORDINATES2['x_start']))
    y_start = int(os.getenv('y_start', DEFAULT_COORDINATES2['y_start']))
    x_end = int(os.getenv('x_end', DEFAULT_COORDINATES2['x_end']))
    y_end = int(os.getenv('y_end', DEFAULT_COORDINATES2['y_end']))
    print(x_start, y_start, x_end, y_end)


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
    global rect_id, x_start, y_start, x_end, y_end

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
    global pdf_path, current_page, pdf
    try:
        pdf_path = filedialog.askopenfilename(filetypes=[("PDF файлы", "*.pdf")])
        if pdf_path:
            entry_pdf_path.delete(0, tk.END)
            entry_pdf_path.insert(0, pdf_path)
            current_page = 0
            load_page()
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось выбрать или загрузить PDF: {e}")


# Функция загрузки и отображения страницы PDF
def load_page():
    global image_display, pdf, current_page, page_image, scale_factor, page_width2, page_height2
    if not pdf_path:
        return
    try:
        with fitz.open(pdf_path) as pdf:
            current_page = max(0, min(current_page, pdf.page_count - 1))
            page = pdf.load_page(current_page)
            pix = page.get_pixmap(dpi=150)

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


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
            label_page_number.config(text=f"Страница: {current_page + 1}/{pdf.page_count}")

            # Обновление информации о размере страницы (Page Size)
            page_size_text = f"{pix.width}x{pix.height}"  # Размеры страницы в пикселях
            label_page_size.config(text=f"Page Size: {page_size_text}")

            # Обновление масштаба (Scale)
            scale_text = f"{scale_factor*100}%"  # Масштаб в процентах
            label_scale.config(text=f"Scale: {scale_text}")

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
    global x_start, y_start, x_end, y_end, cropped_image_display, cropped_image
    x_end, y_end = event.x, event.y

    label_coordinates.configure(text=f"Координаты: ({x_start}, {y_start}) -> ({x_end}, {y_end})")
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
    global x_start, y_start, x_end, y_end
    if x_start is not None and y_start is not None and x_end is not None and y_end is not None:
        label_coordinates.config(
            text=f"Координаты: x={x_start}, y={y_start}, width={x_end - x_start}, height={y_end - y_start}")

def update_coordinates_entry():
    global x_start, y_start, x_end, y_end
    if x_start is not None and y_start is not None and x_end is not None and y_end is not None:
        coordinates_text = f"{x_start},{y_start},{x_end},{y_end}"
        coordinates_entry.delete(0, tk.END)
        coordinates_entry.insert(0, coordinates_text)


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

def start_recognition():
    global pdf_path, x_start, y_start, x_end, y_end

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



def check_image():
    global x_start, y_start, x_end, y_end, current_page, pdf_path

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

            # Распознавание текста
            extracted_text = pytesseract.image_to_string(open_cv_image, lang='eng').strip()

            # Вывод распознанного текста в консоль
            print("Распознанный текст:")
            print(extracted_text)

            # Обновление текстового поля (если используется)
            text_output.delete(1.0, "end")
            text_output.insert("end", extracted_text)

    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось обработать изображение: {e}")




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
def set_default_coordinates():
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
    global canvas2_scale, cropped_image, cropped_image_display, page_image
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
    global x_start, y_start, x_end, y_end
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
def save_env(x_start, y_start, x_end, y_end):
    set_key(ENV_FILE, 'x_start', str(x_start))
    set_key(ENV_FILE, 'y_start', str(y_start))
    set_key(ENV_FILE, 'x_end', str(x_end))
    set_key(ENV_FILE, 'y_end', str(y_end))

# Обработчик выхода
def on_closing():
    global x_start, y_start, x_end, y_end
    save_env(x_start, y_start, x_end, y_end)
    root.destroy()

class TextRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        self.widget.insert(tk.END, text)
        self.widget.see(tk.END)  # Прокрутка текста вниз

    def flush(self):
        pass  # Для совместимости с sys.stdout



# Создание интерфейса
root = tk.Tk()
root.title("Распознавание текста из PDF")
root.protocol("WM_DELETE_WINDOW", on_closing)

# Устанавливаем размеры окна (например, 400x300)
window_width = 800
window_height = 900

# Получаем размеры экрана
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
# Находим точку середины экрана
screen_center_x = screen_width // 2
screen_center_y = screen_height // 2
# Находим точку середины окна
window_center_x = window_width // 2
window_center_y = window_height // 2
# Вычисляем координаты верхнего левого угла, чтобы окно было по центру экрана
x = screen_center_x - window_center_x
y = screen_center_y - window_center_y
# Устанавливаем положение окна
root.geometry(f'{window_width}x{window_height}+{x}+{y}')




# Создание верхней рамки
frame_top = tk.Frame(root)
frame_top.pack(pady=10, padx=10, fill="x")

button_select_pdf = tk.Button(frame_top, text="Выбрать PDF", command=select_pdf)
button_select_pdf.grid(row=0, column=0, padx=5, pady=5)

entry_pdf_path = tk.Entry(frame_top, width=50)
entry_pdf_path.grid(row=0, column=1, padx=5, pady=5)

button_start_recognition = tk.Button(frame_top, text="Запуск распознавания", command=start_recognition_thread)
button_start_recognition.grid(row=0, column=2, padx=5, pady=5)

button_check_image = tk.Button(frame_top, text="Проверка", command=check_image)
button_check_image.grid(row=0, column=3, padx=5, pady=5)

# Создание рамки для элементов управления навигацией
frame_controls = tk.Frame(root)
frame_controls.pack(pady=5, padx=10, fill="x")

button_prev_page = tk.Button(frame_controls, text="Предыдущая страница", command=prev_page)
button_prev_page.grid(row=0, column=0, padx=5, pady=5)

button_next_page = tk.Button(frame_controls, text="Следующая страница", command=next_page)
button_next_page.grid(row=0, column=1, padx=5, pady=5)

button_zoom_out = tk.Button(frame_controls, text="-10%", command=zoom_out)
button_zoom_out.grid(row=0, column=2, padx=5, pady=5)

button_zoom_in = tk.Button(frame_controls, text="+10%", command=zoom_in)
button_zoom_in.grid(row=0, column=3, padx=5, pady=5)

label_page_number = tk.Label(frame_controls, text="Страница: -/-")
label_page_number.grid(row=0, column=4, padx=5, pady=5)

# Новая рамка для поля "Page Size" и "Scale"
frame_settings = tk.Frame(root)
frame_settings.pack(pady=10, padx=10, fill="x")

# Label и поле для выбора "Page Size"
label_page_size = tk.Label(frame_settings, text="Page Size")
label_page_size.grid(row=0, column=0, padx=5, pady=5)

page_size_entry = tk.Entry(frame_settings, width=10)
page_size_entry.grid(row=0, column=1, padx=5, pady=5)

# Label и поле для выбора "Scale"
label_scale = tk.Label(frame_settings, text="Scale")
label_scale.grid(row=0, column=2, padx=5, pady=5)

scale_entry = tk.Entry(frame_settings, width=10)
scale_entry.grid(row=0, column=3, padx=5, pady=5)

# Создание фрейма для координат и поля ввода
frame_coordinates = tk.Frame(root)
frame_coordinates.pack(pady=5, padx=10, fill="x")

coordinates_entry = tk.Entry(frame_coordinates, width=50)
coordinates_entry.grid(row=0, column=0, padx=5, pady=5, sticky="w")

# Привязываем обработчик к полю ввода
coordinates_entry.bind("<KeyRelease>", update_coordinates)

label_coordinates = tk.Label(frame_coordinates, text="Координаты: -")
label_coordinates.grid(row=0, column=1, padx=5, pady=5, sticky="w")

set_default_coordinates()

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
canvas_scale = 1.0
canvas2_scale = 1.0

canvas2.bind("<MouseWheel>", zoom_canvas2)

text_output = scrolledtext.ScrolledText(root, width=100, height=10)
text_output.pack(side=tk.BOTTOM, fill="x", pady=10, padx=10)

text_output.config(state='normal')

sys.stdout = TextRedirector(text_output)

set_tesseract_path()
# Инициализация приложения
#check_and_create_env()
params = read_env()

print(x_start, y_start, x_end, y_end)
root.mainloop()

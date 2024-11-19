import tkinter as tk
from tkinter import ttk, scrolledtext

# Импортируйте все необходимые функции и переменные
from main import select_pdf, start_recognition_thread, check_image, save_current_page, prev_page, next_page
from main import zoom_out, zoom_in, define_coordinates, draw_rectangle, finish_coordinates, update_coordinates
from main import set_default_coordinates, on_closing, zoom_canvas2

def create_interface():
    global root, entry_pdf_path, canvas, label_page_number, label_page_size, label_scale, coordinates_entry
    global canvas2, canvas2_scale, label_coordinates, text_output, regex_pattern_entry, recognition_mode

    # Создание интерфейса
    root = tk.Tk()
    root.title("Распознавание текста из PDF")
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Устанавливаем размеры окна
    window_width = 800
    window_height = 1000
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    root.geometry(f'{window_width}x{window_height}+{x}+{y}')

    # Верхняя рамка
    frame_top = tk.Frame(root)
    frame_top.pack(pady=10, padx=10, fill="x")

    # Группировка элементов в верхней рамке
    elements_top = [
        (tk.Button(frame_top, text="Выбрать PDF", command=select_pdf), 0, 0),
        (tk.Entry(frame_top, width=50), 0, 1),
        (tk.Button(frame_top, text="Запуск распознавания", command=start_recognition_thread), 0, 2)
    ]
    for element, row, col in elements_top:
        element.grid(row=row, column=col, padx=5, pady=5)

    entry_pdf_path = elements_top[1][0]  # Привязка поля ввода для глобального использования

    # Рамка для элементов управления
    frame_controls = tk.Frame(root)
    frame_controls.pack(pady=5, padx=10, fill="x")

    # Группировка элементов управления
    elements_controls = [
        (tk.Button(frame_controls, text="Проверить", command=check_image), 0, 3),
        (tk.Button(frame_controls, text="Сохранить текущий лист", command=save_current_page), 0, 4),
        (tk.Checkbutton(frame_controls, text="Расширенный режим распознавания", variable=tk.IntVar(value=0)), 0, 5)
    ]
    for element, row, col in elements_controls:
        element.grid(row=row, column=col, padx=5, pady=5)

    recognition_mode = elements_controls[2][0].cget('variable')  # Привязка переменной режима

    # Рамка для шаблона поиска текста
    frame_pattern = tk.Frame(root)
    frame_pattern.pack(pady=5, padx=10, fill="x")
    tk.Label(frame_pattern, text="Шаблон поиска текста (рег. выражение):").pack(side=tk.LEFT, padx=5)
    regex_pattern_entry = tk.Entry(frame_pattern, width=40)
    regex_pattern_entry.pack(side=tk.LEFT, padx=5)
    regex_pattern_entry.insert(0, r"^[A-Z]{4}\d{7}$")  # Пример шаблона

    # Рамка для навигации
    frame_navigation = tk.Frame(root)
    frame_navigation.pack(pady=5, padx=10, fill="x")
    elements_navigation = [
        (tk.Button(frame_navigation, text="Предыдущая страница", command=prev_page), 0, 0),
        (tk.Button(frame_navigation, text="Следующая страница", command=next_page), 0, 1),
        (tk.Button(frame_navigation, text="-10%", command=zoom_out), 0, 2),
        (tk.Button(frame_navigation, text="+10%", command=zoom_in), 0, 3),
        (tk.Label(frame_navigation, text="Страница: -/-"), 0, 4)
    ]
    for element, row, col in elements_navigation:
        element.grid(row=row, column=col, padx=5, pady=5)

    label_page_number = elements_navigation[4][0]  # Привязка метки страницы




    # Рамка для "Page Size" и "Scale"
    frame_settings = tk.Frame(root)
    frame_settings.pack(pady=10, padx=10, fill="x")
    elements_settings = [
        (tk.Label(frame_settings, text="Page Size"), 0, 0),
        (tk.Entry(frame_settings, width=10), 0, 1),
        (tk.Label(frame_settings, text="Scale"), 0, 2),
        (tk.Entry(frame_settings, width=10), 0, 3)
    ]
    for element, row, col in elements_settings:
        element.grid(row=row, column=col, padx=5, pady=5)

    label_page_size = elements_settings[0][0]  # Привязка меток для глобального использования
    label_scale = elements_settings[2][0]




    # Рамка для координат
    frame_coordinates = tk.Frame(root)
    frame_coordinates.pack(pady=5, padx=10, fill="x")
    coordinates_entry = tk.Entry(frame_coordinates, width=50)
    coordinates_entry.grid(row=0, column=0, padx=5, pady=5, sticky="w")
    coordinates_entry.bind("<KeyRelease>", update_coordinates)
    label_coordinates = tk.Label(frame_coordinates, text="Координаты: -")
    label_coordinates.grid(row=0, column=1, padx=5, pady=5, sticky="w")



    # Рамка для холстов
    frame_canvases = tk.Frame(root)
    frame_canvases.pack(pady=10, padx=10, fill="both", expand=True)
    canvas_width = 750 // 2
    canvas_height = 500

    # Создание холстов
    canvas = tk.Canvas(frame_canvases, width=canvas_width, height=canvas_height, bg="grey")
    canvas.pack(side=tk.LEFT, anchor=tk.N, padx=5, pady=10)

    canvas2 = tk.Canvas(frame_canvases, width=canvas_width, height=canvas_height, bg="grey")
    canvas2.pack(side=tk.LEFT, anchor=tk.N, padx=5, pady=10)

    canvas.bind("<Button-1>", define_coordinates)
    canvas.bind("<B1-Motion>", draw_rectangle)
    canvas.bind("<ButtonRelease-1>", finish_coordinates)
    canvas2.bind("<MouseWheel>", zoom_canvas2)

    # Рамка для индикатора прогресса
    frame_progress = tk.Frame(root)
    frame_progress.pack(pady=5, padx=10, fill="x")
    progress_bar = ttk.Progressbar(frame_progress, orient="horizontal", length=300, mode="indeterminate")
    progress_bar.pack(pady=5)

    # Поле для вывода текста
    text_output = scrolledtext.ScrolledText(root, width=100, height=10)
    text_output.pack(side=tk.BOTTOM, fill="x", pady=10, padx=10)
    text_output.config(state='normal')

    # Установка значений по умолчанию
    set_default_coordinates(coordinates_entry)


###############











    # Создание рамки для холстов
    frame_canvases = tk.Frame(root)
    frame_canvases.pack(pady=10, padx=10, fill="both", expand=True)

    # Настройка холстов
    canvas_width = 750 // 2
    canvas_height = 500

    # Группировка холстов в рамке
    canvases = [
        (tk.Canvas(frame_canvases, width=canvas_width, height=canvas_height, bg="grey"), tk.LEFT),
        (tk.Canvas(frame_canvases, width=canvas_width, height=canvas_height, bg="grey"), tk.LEFT)
    ]

    for canvas, side in canvases:
        canvas.pack(side=side, anchor=tk.N, padx=5, pady=10)

    # Привязка событий к первому холсту
    canvases[0][0].bind("<Button-1>", define_coordinates)
    canvases[0][0].bind("<B1-Motion>", draw_rectangle)
    canvases[0][0].bind("<ButtonRelease-1>", finish_coordinates)

    # Масштаб для второго холста
    canvas2_scale = 1.0
    canvases[1][0].bind("<MouseWheel>", zoom_canvas2)

    # Создание текстового поля для вывода
    text_output = scrolledtext.ScrolledText(root, width=100, height=10)
    text_output.pack(side=tk.BOTTOM, fill="x", pady=10, padx=10)
    text_output.config(state='normal')
    sys.stdout = TextRedirector(text_output)

    # Установка начальных координат
    set_default_coordinates(coordinates_entry)

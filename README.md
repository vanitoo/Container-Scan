# PDF Text Recognition Tool

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.5+-green.svg)
![Tesseract](https://img.shields.io/badge/Tesseract-OCR-yellowgreen)


# OpenCV PDF Text Recognizer

Инструмент для автоматического распознавания текста из PDF-файлов с поддержкой нескольких OCR-движков  (Tesseract, EasyOCR, PaddleOCR) и возможностью сравнения с эталонными данными.


---

## 🚀 Возможности

* 📄 Загрузка PDF и XLS файлов
* 🔍 Просмотр, выделение и распознавание текста на страницах
* 🧠 Поддержка нескольких OCR движков
* - Tesseract (обязательный)
  - EasyOCR (опционально)
  - PaddleOCR (опционально)
* 🗂 Сопоставление с эталонными данными
* 💾 Сохранение результатов и отдельных листов
* ⚙️ Расширенные опции (режимы, координаты, шаблоны)
* 🔄 Автообновление через GitHub Releases

---

## 📦 Установка

```bash
pip install -r requirements.txt
```

### Зависимости:

* Python 3.11+
* Tesseract OCR (установить отдельно)
* `pytesseract`, `tkinter`, `requests`, `openpyxl`, `Pillow`, `packaging`

---

## 🧠 Использование

```bash
python main.py
```

* Выберите PDF и XLS
* Установите зону распознавания (или используйте шаблон)
* Запустите распознавание
* Сравните с эталоном, сохраните результат

---

## 🔄 Обновление

Программа автоматически проверяет актуальную версию через GitHub:

```
https://github.com/vanitoo/pythonProject-OpenCV-PDF/releases/latest
```

При наличии новой версии, загружается `main_new.exe` и предлагается обновление.

---

## 📁 Структура проекта

```bash
project/
├── main.py               # основной GUI-интерфейс
├── auto_updater.py       # автообновление
├── version.py            # текущая версия
├── requirements.txt
└── README.md
```

---

## 🛠 Переменные окружения

Файл `.env` может содержать:

```
X=20
Y=298
W=72
H=47
```

---

## 🧩 Дополнительно

* 📌 Программа сохраняет временные логи в `text_output`
* 🧪 Поддерживает режим отладки (`Debug`)
* 🔧 Расширенные поля координат и шаблонов

---

## 📬 Обратная связь

[Открыть GitHub Issue](https://github.com/vanitoo/pythonProject-OpenCV-PDF/issues)

---

## 🧑‍💻 Автор

Разработка: [@vanitoo](https://github.com/vanitoo)

Лицензия: MIT

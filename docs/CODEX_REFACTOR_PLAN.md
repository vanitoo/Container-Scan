# План для Codex: безопасный рефакторинг PDF OCR проекта

Репозиторий: `vanitoo/container-scan`

Цель: продолжить безопасный рефакторинг PDF/OCR-приложения без поломки текущего GUI и рабочей логики.

Важно: этот проект относится только к PDF/OCR-распознаванию и сверке с Excel/CSV. Не смешивать с проектом квитанций, Word-шаблонов, PDF-генерации квитанций и почтовой рассылки.

---

## Текущее состояние

Уже сделано:

1. Обновлён `README.md` с текущей архитектурой и планом рефакторинга.
2. Очищен `services/excel_service.py`:
   - убран старый метод `load_registry2`;
   - оставлен один актуальный `load_registry`;
   - поведение не менялось.
3. Очищен `models/state.py`:
   - убраны устаревшие комментарии;
   - временные обратные ссылки `gui`, `tree`, `pdf_service`, `ocr_service` оставлены и явно помечены как временные.
4. Очищен `services/pdf_service.py`:
   - локальные импорты перенесены наверх;
   - удалены старые закомментированные куски;
   - рабочая логика не менялась.
5. Удалены устаревшие файлы:
   - `pyproject.toml2`;
   - `.github/workflows/*_old`.

---

## Главное правило

Не делать большой архитектурный рефакторинг одним коммитом.

Каждый шаг должен быть маленьким, проверяемым и откатываемым.

После каждого изменения:

```bash
python -m compileall .
ruff check .
python run.py
```

Если GUI не запускается — откатить последний коммит.

---

## Запрещено на текущем этапе

До отдельного этапа нельзя:

- переименовывать публичные методы GUI;
- менять сигнатуры методов, которые вызываются кнопками Tkinter;
- удалять методы из `MainWindow`, даже если они выглядят дублирующимися;
- менять логику OCR;
- менять порядок колонок таблицы;
- менять формат `state.table_entries`;
- менять формат `state.selected_areas`;
- менять сохранение файлов результатов;
- подключать EasyOCR/PaddleOCR;
- делать автоформатирование всего проекта без проверки.

---

## Этап 2.1 — безопасная чистка `gui/main_window.py`

Файл: `gui/main_window.py`

Цель: убрать только очевидный мусор, не меняя поведение.

### Что можно сделать

1. Убрать дубли импортов в начале файла.

Сейчас вверху есть повторный блок импортов. Нужно оставить один чистый блок:

```python
from __future__ import annotations

import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from PIL import Image

from config import WINDOW_SIZE
from gui.components import CanvasComponent, StatusBar, TableComponent, TextRedirector
from gui.themes import apply_minimal_theme, toggle_theme
from utils.logger import logger
from utils.updater import AutoUpdater
```

Если `toggle_theme` используется только внутри `_toggle_theme`, можно оставить импорт на верхнем уровне и убрать локальный импорт внутри метода.

2. Убрать служебные комментарии после ручной склейки:

- `# gui/main_window.py (добавляем в начало файла)`
- `# gui/main_window.py (обновляем методы навигации)`
- похожие комментарии вида `добавляем`, `обновляем`, если они описывают не логику, а историю правок.

3. Не удалять обычные поясняющие комментарии, которые объясняют поведение GUI.

4. Не удалять методы:

- `update_debug_mode`
- `_update_debug_mode`
- `toggle_theme`
- `_toggle_theme`
- `init_ocr_engine`
- `_init_ocr_engine`
- `update_coordinates`
- `_update_coordinates`

Даже если часть из них сейчас выглядит неиспользуемой. Их можно разбирать только после поиска вызовов по всему проекту.

### Проверка после этапа 2.1

```bash
python -m compileall gui/main_window.py
ruff check gui/main_window.py
python run.py
```

Ручная проверка:

- окно открывается;
- кнопка выбора PDF открывает диалог;
- кнопка выбора XLS открывает диалог;
- панель Options раскрывается;
- переключатель Debug не падает;
- кнопка темы не падает;
- поле координат отображается.

Коммит:

```text
refactor: cleanup main window imports and stale comments
```

---

## Этап 2.2 — безопасная чистка `gui/components.py`

Файл: `gui/components.py`

Цель: убрать только очевидный мусор без изменения логики canvas/table.

### Что можно сделать

1. Проверить импорты.

Если `logging`, `scrolledtext`, `webbrowser`, `DOUBLE_CLICK_DELAY` реально не используются — удалить.

Перед удалением обязательно выполнить поиск по файлу.

2. Убрать служебный комментарий:

```python
# gui/components.py (добавляем в класс CanvasComponent)
```

3. Не удалять `on_canvas_release_new`, даже если он пока не привязан к событию.

Причина: это заготовка для следующего этапа с нормализованными координатами.

4. Не менять binding:

```python
self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
```

На этом этапе не переключать на `on_canvas_release_new`.

### Проверка после этапа 2.2

```bash
python -m compileall gui/components.py
ruff check gui/components.py
python run.py
```

Ручная проверка:

- PDF отображается на canvas;
- выделение мышкой работает;
- второй canvas с crop не падает;
- zoom колесом мыши не падает.

Коммит:

```text
refactor: cleanup gui components imports and stale comments
```

---

## Этап 2.3 — минимальная проверка всего проекта

После чистки GUI:

```bash
python -m compileall .
ruff check .
```

Если Ruff показывает много старых ошибок, не исправлять всё одним махом. Сначала зафиксировать список в отдельном файле:

```text
docs/RUFF_TODO.md
```

Коммит:

```text
chore: document remaining ruff issues
```

---

## Этап 3 — единая модель координат

К этому этапу переходить только после завершения чистки GUI.

Цель: убрать расхождение между экранными координатами и координатами OCR.

### План

1. Создать новый файл:

```text
models/selection.py
```

2. Добавить dataclass:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SelectionRect:
    x1_norm: float
    y1_norm: float
    x2_norm: float
    y2_norm: float

    def normalized(self) -> "SelectionRect":
        x1, x2 = sorted((self.x1_norm, self.x2_norm))
        y1, y2 = sorted((self.y1_norm, self.y2_norm))
        return SelectionRect(
            max(0.0, min(1.0, x1)),
            max(0.0, min(1.0, y1)),
            max(0.0, min(1.0, x2)),
            max(0.0, min(1.0, y2)),
        )

    def to_pixel_box(self, width: int, height: int) -> tuple[int, int, int, int]:
        rect = self.normalized()
        return (
            int(round(rect.x1_norm * width)),
            int(round(rect.y1_norm * height)),
            int(round(rect.x2_norm * width)),
            int(round(rect.y2_norm * height)),
        )
```

3. Добавить тесты на `SelectionRect` до внедрения в GUI.

4. Только после тестов начать подключать `SelectionRect` к `CanvasComponent`.

### Важно

На этапе 3 не удалять старый `selected_areas` сразу. Сначала вести обе модели параллельно:

- старая модель нужна для обратной совместимости;
- новая нужна для OCR.

Коммит 1:

```text
feat: add normalized selection model
```

Коммит 2:

```text
test: add selection model tests
```

Коммит 3:

```text
refactor: store normalized selection from canvas
```

---

## Этап 4 — отвязка сервисов от Tkinter

Переходить только после этапа 3.

Цель: сделать сервисы тестируемыми без GUI.

### ExcelService

Сейчас `ExcelService` обновляет `state.gui.tree`.

Нужно постепенно привести к модели:

```python
records = excel_service.load_registry(file_path)
gui.apply_registry_records(records)
```

Но не делать это одним коммитом.

Шаги:

1. Добавить метод `read_registry(file_path) -> list[tuple[str, str]]`.
2. Оставить старый `load_registry()` как обёртку, чтобы GUI не сломался.
3. Перевести GUI на новый метод.
4. После проверки удалить старую связку.

### MatchingService

Сейчас `MatchingService` принимает `tree_widget` и красит строки.

Нужно постепенно привести к модели:

```python
matches = matching_service.match_entries(table_entries, expected_containers)
gui.apply_match_results(matches)
```

---

## Этап 5 — OCR engine interface

Переходить только после этапов 2–4.

Цель: подготовить архитектуру под Tesseract/EasyOCR/PaddleOCR.

Структура:

```text
services/ocr/
├── __init__.py
├── base.py
├── preprocessing.py
├── tesseract_engine.py
├── easyocr_engine.py
└── paddleocr_engine.py
```

На первом шаге реализовать только Tesseract через интерфейс.

Не подключать тяжёлые зависимости EasyOCR/PaddleOCR сразу.

---

## Рекомендуемый порядок ближайших коммитов

```text
refactor: cleanup main window imports and stale comments
refactor: cleanup gui components imports and stale comments
chore: document remaining ruff issues
feat: add normalized selection model
test: add selection model tests
refactor: store normalized selection from canvas
```

---

## Как проверять руками

Минимальный smoke-test после каждого GUI-коммита:

1. Запустить:

```bash
python run.py
```

2. Проверить:

- окно открывается;
- Options открывается/закрывается;
- Debug включается/выключается;
- тема переключается;
- PDF выбирается;
- страница отображается;
- выделение мышкой рисуется;
- crop показывается на втором canvas;
- `Проверить лист` не падает;
- `Запуск распознавания` не падает при выбранной области;
- XLS/CSV выбирается;
- `Сопоставить` не падает;
- `Сохранить лист` не падает.

---

## Если что-то сломалось

1. Не продолжать следующие этапы.
2. Посмотреть последний коммит:

```bash
git log --oneline -5
```

3. Откатить последний коммит:

```bash
git revert <sha>
```

4. Повторить правку меньшим объёмом.

---

## Главная цель ближайшей итерации

Не улучшать функциональность.

Сначала сделать код чище и безопаснее для следующего этапа.

Основной результат ближайшей итерации: `main_window.py` и `components.py` должны стать чище, но приложение должно вести себя точно так же, как до правки.

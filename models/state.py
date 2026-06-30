# models/state.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import fitz
from PIL import Image

from config import DEFAULT_COORDINATES


@dataclass
class AppState:
    # PDF состояние
    pdf_doc: Optional[fitz.Document] = None
    pdf_path: Optional[str] = None
    current_page: int = 0
    total_pages: int = 0
    is_temp_pdf: bool = False

    # Изображения
    page_image: Optional[Image.Image] = None
    original_page_image: Optional[Image.Image] = None
    image_display: Any = None
    cropped_image: Optional[Image.Image] = None

    # Координаты и выделение
    x_start: int = field(default_factory=lambda: DEFAULT_COORDINATES["X_START"])
    y_start: int = field(default_factory=lambda: DEFAULT_COORDINATES["Y_START"])
    x_end: int = field(default_factory=lambda: DEFAULT_COORDINATES["X_END"])
    y_end: int = field(default_factory=lambda: DEFAULT_COORDINATES["Y_END"])
    rect_id: Any = None
    selected_areas: List = field(default_factory=list)
    selection_rect_norm: Optional[tuple] = None

    # Масштабирование
    scale_factor: float = 1.0
    last_scale_factor: float = 1.0
    canvas_scale: float = 1.0
    canvas2_scale: float = 1.0

    # OCR
    ocr_engine: str = "Tesseract"
    ocr_reader: Any = None
    recognition_results: List[Dict] = field(default_factory=list)
    regex_pattern: str = field(default_factory=lambda: DEFAULT_COORDINATES["REGEX_PATTERN"])

    # Табличные данные
    table_entries: List[Dict] = field(default_factory=list)
    all_excel_records: List = field(default_factory=list)
    expected_containers: List[str] = field(default_factory=list)

    # Настройки UI
    current_theme: str = "light"
    debug_mode: bool = False
    extra_mode: bool = False
    recognition_mode: int = 0

    # Флаги
    download_cancelled: bool = False

    # Временные обратные ссылки. Будут убраны на этапе разделения GUI и сервисов.
    pdf_service: Any = None
    ocr_service: Any = None
    gui: Any = None
    tree: Any = None

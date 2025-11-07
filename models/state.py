# models/state.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
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
    is_temp_pdf: bool = False  # этот PDF создан программно (временный) и его можно удалять при выгрузке

    # Изображения
    page_image: Optional[Image.Image] = None
    original_page_image: Optional[Image.Image] = None
    image_display: Any = None
    cropped_image: Optional[Image.Image] = None

    # Координаты и выделение
    # x_start: int = 20
    # y_start: int = 298
    # x_end: int = 92
    # y_end: int = 345
    x_start: int = field(default_factory=lambda: DEFAULT_COORDINATES["X_START"])
    y_start: int = field(default_factory=lambda: DEFAULT_COORDINATES["Y_START"])
    x_end:   int = field(default_factory=lambda: DEFAULT_COORDINATES["X_END"])
    y_end:   int = field(default_factory=lambda: DEFAULT_COORDINATES["Y_END"])
    rect_id: Any = None
    selected_areas: List = field(default_factory=list)
    selection_rect_norm: Optional[tuple] = None  # (x1n, y1n, x2n, y2n) в [0..1]

    # Масштабирование
    scale_factor: float = 1.0
    last_scale_factor: float = 1.0
    canvas_scale: float = 1.0
    canvas2_scale: float = 1.0

    # OCR
    ocr_engine: str = "Tesseract"
    ocr_reader: Any = None
    recognition_results: List[Dict] = field(default_factory=list)

    # Табличные данные
    table_entries: List[Dict] = field(default_factory=list)
    all_excel_records: List = field(default_factory=list)
    expected_containers: List[str] = field(default_factory=list)

    # Настройки UI
    current_theme: str = "light"
    debug_mode: bool = False
    extra_mode: bool = False
    recognition_mode: int = 0  # 0=Basic, 1=Advance

    # Флаги
    download_cancelled: bool = False

    # models/state.py (добавляем в класс AppState)
    # regex_pattern: str = r"^[A-Z]{3}U\d{7}$"
    regex_pattern: str = field(default_factory=lambda: DEFAULT_COORDINATES["REGEX_PATTERN"])
    pdf_service: Any = None
    ocr_service: Any = None
    gui: Any = None
    tree: Any = None
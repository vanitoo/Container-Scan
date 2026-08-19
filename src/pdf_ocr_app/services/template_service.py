from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

from pdf_ocr_app.utils.logger import logger


class TemplateService:
    """Load fixed form templates and their field definitions."""

    TEMPLATE_DIR = Path("templates") / "smgs_01"
    TEMPLATE_RELATIVE_PATH = TEMPLATE_DIR / "template.png"
    FIELDS_RELATIVE_PATH = TEMPLATE_DIR / "fields.json"

    @staticmethod
    def resource_root() -> Path:
        if getattr(sys, "frozen", False):
            return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return Path(__file__).resolve().parents[3]

    def load_smgs_01(self) -> Image.Image:
        template_path = self.resource_root() / self.TEMPLATE_RELATIVE_PATH
        if not template_path.is_file():
            raise FileNotFoundError(f"Шаблон не найден: {template_path}")

        image = Image.open(template_path).convert("RGB")
        logger.info(
            f"Загружен шаблон SMGS-01: {template_path} ({image.width}x{image.height})"
        )
        return image

    def load_smgs_01_fields(self) -> dict:
        fields_path = self.resource_root() / self.FIELDS_RELATIVE_PATH
        if not fields_path.is_file():
            raise FileNotFoundError(f"Разметка шаблона не найдена: {fields_path}")

        data = json.loads(fields_path.read_text(encoding="utf-8"))
        if not isinstance(data.get("fields"), dict):
            raise ValueError("fields.json не содержит объекта fields")
        return data

    def get_smgs_01_field_box(self, field_name: str, image: Image.Image) -> tuple[int, int, int, int]:
        data = self.load_smgs_01_fields()
        field = data["fields"].get(field_name)
        if not isinstance(field, dict):
            raise KeyError(f"Поле шаблона не найдено: {field_name}")

        box = field.get("box_norm")
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError(f"Поле {field_name} не содержит корректный box_norm")

        x1, y1, x2, y2 = (float(value) for value in box)
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError(f"Некорректные нормализованные координаты поля {field_name}: {box}")

        pixel_box = (
            round(x1 * image.width),
            round(y1 * image.height),
            round(x2 * image.width),
            round(y2 * image.height),
        )
        logger.info(f"SMGS-01 поле {field_name}: norm={box}, pixels={pixel_box}")
        return pixel_box

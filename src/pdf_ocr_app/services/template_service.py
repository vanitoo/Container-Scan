from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

from pdf_ocr_app.utils.logger import logger


class TemplateService:
    """Load fixed form templates bundled with the application."""

    TEMPLATE_RELATIVE_PATH = Path("templates") / "smgs_01" / "template.png"

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

from __future__ import annotations

from pathlib import Path

import pytesseract

from config import TESSERACT_PATHS
from utils.logger import logger

from .base import EngineInitResult, OCRBackend
from .preprocessing import prepare_tesseract_image

TESSERACT_INSTALL_URL = "https://github.com/UB-Mannheim/tesseract/wiki"


class TesseractEngine(OCRBackend):
    name = "Tesseract"
    install_hint = f"Установить Tesseract можно здесь: {TESSERACT_INSTALL_URL}"

    def __init__(self):
        self.tesseract_path: Path | None = None

    def is_installed(self) -> bool:
        for path in TESSERACT_PATHS:
            if path.exists():
                self.tesseract_path = path
                return True

        self.tesseract_path = None
        return False

    def initialize(self) -> EngineInitResult:
        if not self.is_installed():
            message = "Tesseract не найден."
            logger.error(message)
            logger.info(self.install_hint)
            return EngineInitResult(False, self.name, message, self.install_hint)

        pytesseract.pytesseract.tesseract_cmd = str(self.tesseract_path)

        try:
            version = pytesseract.get_tesseract_version()
            message = f"Tesseract доступен: {pytesseract.pytesseract.tesseract_cmd} ({version})"
            logger.info(message)
            return EngineInitResult(True, self.name, message)
        except Exception as exc:
            message = f"Tesseract найден, но не запускается: {exc}"
            logger.error(message)
            logger.info(self.install_hint)
            return EngineInitResult(False, self.name, message, self.install_hint)

    def recognize(self, image) -> str:
        return pytesseract.image_to_string(image, lang="eng").strip()

    def recognize_advanced(self, image, **kwargs) -> str:
        prepared_image = prepare_tesseract_image(image, **kwargs)
        return pytesseract.image_to_string(prepared_image, lang="eng").strip().upper()

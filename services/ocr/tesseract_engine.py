from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
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
        data = pytesseract.image_to_data(
            image,
            lang="eng",
            config="--psm 11",
            output_type=pytesseract.Output.DICT,
        )

        candidates = []
        for index, text in enumerate(data["text"]):
            cleaned = re.sub(r"[^A-Z0-9]", "", text.upper())
            if re.fullmatch(r"[A-Z]{3}U\d{7}", cleaned):
                return cleaned
            if re.match(r"^[A-Z]{3}U", cleaned) and 9 <= len(cleaned) <= 13:
                candidates.append(index)

        source = np.asarray(image)
        if source.ndim == 3:
            # PDFService returns OpenCV images in BGR order.
            source = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)

        for index in candidates:
            x = int(data["left"][index])
            y = int(data["top"][index])
            width = int(data["width"][index])
            height = int(data["height"][index])
            padding_x = max(4, round(width * 0.08))
            padding_y = max(3, round(height * 0.25))
            word_image = source[
                max(0, y - padding_y):min(source.shape[0], y + height + padding_y),
                max(0, x - padding_x):min(source.shape[1], x + width + padding_x),
            ]
            if word_image.size == 0:
                continue

            word_image = cv2.resize(word_image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            _, word_image = cv2.threshold(
                word_image,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )
            retry = pytesseract.image_to_string(
                word_image,
                lang="eng",
                config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            ).strip()
            cleaned_retry = re.sub(r"[^A-Z0-9]", "", retry.upper())
            if cleaned_retry:
                return cleaned_retry

        return pytesseract.image_to_string(image, lang="eng").strip()

    def recognize_advanced(self, image, **kwargs) -> str:
        prepared_image = prepare_tesseract_image(image, **kwargs)
        return pytesseract.image_to_string(prepared_image, lang="eng").strip().upper()

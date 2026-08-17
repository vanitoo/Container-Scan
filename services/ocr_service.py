# services/ocr_service.py
from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

import cv2

from models.state import AppState
from services.ocr import EngineInitResult, TesseractEngine
from services.ocr.easyocr_engine import EasyOCREngine
from services.ocr.paddleocr_engine import PaddleOCREngine
from services.ocr.preprocessing import prepare_tesseract_image
from utils.logger import logger


class OCRService:
    def __init__(self, state: AppState):
        self.state = state
        self.tesseract_engine = TesseractEngine()
        self.easyocr_engine = EasyOCREngine()
        self.paddleocr_engine = PaddleOCREngine()
        self.active_engine = self.tesseract_engine

    def check_tesseract(self) -> bool:
        """Проверка доступности Tesseract при старте приложения."""
        result = self.tesseract_engine.initialize()
        return result.ok

    def initialize_engine(self, engine_name: str) -> EngineInitResult:
        """Инициализация выбранного OCR движка."""
        normalized_engine = (engine_name or "").strip().lower()

        if normalized_engine == "tesseract":
            result = self.tesseract_engine.initialize()
            if result.ok:
                self.active_engine = self.tesseract_engine
                self.state.ocr_engine = self.tesseract_engine.name
            return result

        backend_map = {
            "easyocr": self.easyocr_engine,
            "paddleocr": self.paddleocr_engine,
        }
        backend = backend_map.get(normalized_engine)
        if backend is None:
            message = f"Неизвестный OCR движок: {engine_name}"
            logger.error(message)
            return EngineInitResult(False, engine_name, message)

        if not backend.is_installed():
            message = f"{backend.name} не установлен."
            logger.error(message)
            logger.info(backend.install_hint)
            return EngineInitResult(False, backend.name, message, backend.install_hint)

        message = f"{backend.name} установлен, но на этом этапе ещё не подключён."
        logger.warning(message)
        logger.info("Для распознавания сейчас используется только Tesseract.")
        return EngineInitResult(False, backend.name, message, backend.install_hint)

    def recognize_with_engine(self, image, engine: str | None = None) -> str:
        """Распознавание текста с использованием выбранного движка"""
        if engine is None:
            engine = self.state.ocr_engine

        engine = engine.lower().strip()

        if engine == "tesseract":
            return self.tesseract_engine.recognize(image)

        logger.warning(f"Движок {engine} пока не подключён. Используется Tesseract.")
        return self.tesseract_engine.recognize(image)

    def enhanced_recognition(self, image, **kwargs):
        """Расширенное распознавание с обработкой изображения"""
        prepared_image = prepare_tesseract_image(image, **kwargs)
        return self.tesseract_engine.recognize(prepared_image).upper()

    def format_extracted_text(self, text: str, page_num: int) -> str:
        """Форматирование распознанного текста"""
        # Удаление всех символов, кроме английских букв и цифр
        cleaned_text = re.sub(r"[^A-Za-z0-9]", "", text).upper()

        logger.debug(f"Страница {page_num} - очищенный текст: '{cleaned_text}'")

        # Проверка формата: 3 буквы + U + 7 цифр
        if re.match(r"^[A-Z]{3}U\d{7}$", cleaned_text):
            logger.debug(f"Страница {page_num} - корректный формат: '{cleaned_text}'")
            return cleaned_text

        # Ищем паттерн контейнера в тексте
        container_pattern = r"[A-Z]{3}U\d{7}"
        matches = re.findall(container_pattern, cleaned_text)
        if matches:
            logger.debug(f"Страница {page_num} - найден контейнер в тексте: '{matches[0]}'")
            return matches[0]

        # Если не нашли полный контейнер, ищем частичные совпадения
        if len(cleaned_text) >= 11:
            potential_container = cleaned_text[:11]
            logger.debug(f"Страница {page_num} - потенциальный контейнер: '{potential_container}'")

            formatted_text = ""
            for i, char in enumerate(potential_container):
                if i < 3 and not char.isalpha():
                    formatted_text += "@"
                elif i < 3 and char.islower():
                    formatted_text += char.upper()
                elif i == 3 and char != 'U':
                    formatted_text += 'U'
                elif i > 3 and not char.isdigit():
                    formatted_text += "@"
                else:
                    formatted_text += char

            valid_chars = sum(1 for c in formatted_text if c != '@')
            if valid_chars >= 4:
                logger.debug(f"Страница {page_num} - отформатировано: '{formatted_text}'")
                return formatted_text

        logger.debug(f"Страница {page_num} - не удалось распознать контейнер, исходный текст: '{text}'")
        return "Не распознано"

    def recognize_area(self, page_index: int, coords: tuple) -> str:
        """Распознавание текста в области"""
        try:
            cropped_image = self.state.pdf_service.extract_area_image(page_index, coords)
            if cropped_image is None or cropped_image.size == 0:
                return ""

            if self.state.debug_mode:
                debug_dir = Path("debug_images")
                debug_dir.mkdir(parents=True, exist_ok=True)
                debug_image_path = debug_dir / f"page_{page_index + 1}_debug.jpg"
                cv2.imwrite(str(debug_image_path), cropped_image)
                logger.debug(f"Сохранено отладочное изображение: {debug_image_path}")

            # Выбор режима распознавания
            if self.state.recognition_mode == 1:  # Advance режим
                recognized_text = self.enhanced_recognition(
                    cropped_image,
                    options=self.state.advanced_options,
                    order=self.state.advanced_order,
                )
            else:
                recognized_text = self.recognize_with_engine(cropped_image)

            formatted_text = self.format_extracted_text(recognized_text, page_index + 1)

            # Сохранение результатов
            result = {
                "page": page_index + 1,
                "raw_text": recognized_text,
                "formatted_text": formatted_text,
                "coords": coords,
                "engine": self.state.ocr_engine,
            }

            if len(self.state.recognition_results) > page_index:
                self.state.recognition_results[page_index] = result
            else:
                self.state.recognition_results.append(result)

            logger.info(f"Страница {page_index + 1}: {formatted_text}")
            return formatted_text

        except Exception as e:
            logger.error(f"Ошибка при распознавании области: {e}")
            return ""

    def is_similar_ratio(self, a: str, b: str) -> float:
        """Сравнение схожести строк"""
        return SequenceMatcher(None, a, b).ratio()

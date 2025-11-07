# services/ocr_service.py
from __future__ import annotations

import re
from difflib import SequenceMatcher

import cv2
import numpy as np
import pytesseract
from config import TESSERACT_PATHS
from models.state import AppState
from utils.logger import logger


class OCRService:
    def __init__(self, state: AppState):
        self.state = state
        self.set_tesseract_path()

    def set_tesseract_path(self):
        """Установка пути к Tesseract"""
        for path in TESSERACT_PATHS:
            if path.exists():
                pytesseract.pytesseract.tesseract_cmd = str(path)
                logger.debug(f"Путь для Tesseract установлен: {path}")
                return

        logger.info("Tesseract не найден. Пожалуйста, установите его.")
        logger.info("Ссылка на проект: https://github.com/UB-Mannheim/tesseract/wiki")

    def recognize_with_engine(self, image, engine: str = None) -> str:
        """Распознавание текста с использованием выбранного движка"""
        if engine is None:
            engine = self.state.ocr_engine

        engine = engine.lower().strip()

        if engine == "tesseract":
            return pytesseract.image_to_string(image, lang="eng").strip()

        # TODO: Добавить поддержку EasyOCR и PaddleOCR при необходимости
        # Пока используем Tesseract как fallback
        return pytesseract.image_to_string(image, lang="eng").strip()

    def enhanced_recognition(self, image, **kwargs):
        """Расширенное распознавание с обработкой изображения"""
        use_grayscale = kwargs.get('use_grayscale', True)
        use_median_blur = kwargs.get('use_median_blur', True)
        use_thresholding = kwargs.get('use_thresholding', False)
        use_clahe = kwargs.get('use_clahe', True)
        use_resize = kwargs.get('use_resize', True)
        use_deskew = kwargs.get('use_deskew', False)
        use_noise_removal = kwargs.get('use_noise_removal', True)
        use_morphological_ops = kwargs.get('use_morphological_ops', False)

        if use_grayscale:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if use_median_blur:
            image = cv2.medianBlur(image, 3)

        if use_thresholding:
            _, image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if use_clahe:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            image = clahe.apply(image)

        if use_resize:
            image = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        if use_deskew:
            coords = np.column_stack(np.where(image > 0))
            if len(coords) > 0:
                angle = cv2.minAreaRect(coords)[-1]
                angle = -(90 + angle) if angle < -45 else -angle
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                image = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        if use_noise_removal:
            image = cv2.medianBlur(image, 3)

        if use_morphological_ops:
            kernel = np.ones((1, 1), np.uint8)
            image = cv2.dilate(image, kernel, iterations=1)
            image = cv2.erode(image, kernel, iterations=1)

        return pytesseract.image_to_string(image, lang="eng").strip().upper()

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
                import os
                debug_dir = "debug_images"
                os.makedirs(debug_dir, exist_ok=True)
                debug_image_path = os.path.join(debug_dir, f"page_{page_index + 1}_debug.jpg")
                cv2.imwrite(debug_image_path, cropped_image)
                logger.debug(f"Сохранено отладочное изображение: {debug_image_path}")

            # Выбор режима распознавания
            if self.state.recognition_mode == 1:  # Advance режим
                recognized_text = self.enhanced_recognition(
                    cropped_image,
                    use_grayscale=True,
                    use_median_blur=True,
                    use_thresholding=True,
                    use_clahe=True,
                    use_resize=True,
                    use_deskew=True,
                    use_noise_removal=True,
                    use_morphological_ops=True
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
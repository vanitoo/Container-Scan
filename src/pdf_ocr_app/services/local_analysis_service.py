from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from pdf_ocr_app.models.state import AppState
from pdf_ocr_app.utils.logger import logger


@dataclass
class LocalAnalysisResult:
    status: str
    box: tuple[int, int, int, int] | None
    confidence: float
    method: str
    message: str


class LocalAnalysisService:
    """Уточняет известную область поля без выравнивания всего документа.

    Алгоритм расширяет эталонный прямоугольник, ищет внутри него рамку ячейки
    по контурам/линиям и возвращает уточнённые координаты в пикселях исходного
    отрендеренного листа. Если рамка не найдена достаточно уверенно, используется
    расширенная зона поиска как безопасный fallback для OCR.
    """

    def __init__(self, state: AppState):
        self.state = state

    @staticmethod
    def _expand_box(
        box: tuple[int, int, int, int],
        image_size: tuple[int, int],
        x_margin: float = 0.35,
        y_margin: float = 0.75,
    ) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        image_width, image_height = image_size

        expanded = (
            max(0, round(x1 - width * x_margin)),
            max(0, round(y1 - height * y_margin)),
            min(image_width, round(x2 + width * x_margin)),
            min(image_height, round(y2 + height * y_margin)),
        )
        return expanded

    @staticmethod
    def _score_candidate(
        candidate: tuple[int, int, int, int],
        expected_box: tuple[int, int, int, int],
        search_box: tuple[int, int, int, int],
    ) -> float:
        x, y, w, h = candidate
        ex1, ey1, ex2, ey2 = expected_box
        sx1, sy1, _, _ = search_box

        expected_w = max(1, ex2 - ex1)
        expected_h = max(1, ey2 - ey1)
        expected_ratio = expected_w / expected_h
        ratio = w / max(1, h)

        size_score = min(w / expected_w, expected_w / max(1, w)) * min(
            h / expected_h, expected_h / max(1, h)
        )
        ratio_score = min(ratio / expected_ratio, expected_ratio / max(0.001, ratio))

        expected_cx = (ex1 + ex2) / 2 - sx1
        expected_cy = (ey1 + ey2) / 2 - sy1
        candidate_cx = x + w / 2
        candidate_cy = y + h / 2
        distance = np.hypot(candidate_cx - expected_cx, candidate_cy - expected_cy)
        diagonal = np.hypot(expected_w, expected_h)
        position_score = max(0.0, 1.0 - distance / max(1.0, diagonal * 1.5))

        return float(0.45 * size_score + 0.30 * ratio_score + 0.25 * position_score)

    def analyze(
        self,
        image: Image.Image,
        reference_box: tuple[int, int, int, int],
    ) -> LocalAnalysisResult:
        if image is None:
            return LocalAnalysisResult("FAILED", None, 0.0, "none", "Нет изображения страницы")

        image_width, image_height = image.size
        search_box = self._expand_box(reference_box, (image_width, image_height))
        sx1, sy1, sx2, sy2 = search_box
        if sx2 <= sx1 or sy2 <= sy1:
            return LocalAnalysisResult("FAILED", None, 0.0, "none", "Некорректная зона поиска")

        source = np.asarray(image)
        gray = cv2.cvtColor(source, cv2.COLOR_RGB2GRAY) if source.ndim == 3 else source
        search_gray = gray[sy1:sy2, sx1:sx2]
        if search_gray.size == 0:
            return LocalAnalysisResult("FAILED", None, 0.0, "none", "Пустая зона поиска")

        # Линии таблицы на сканах обычно стабильнее содержимого ячейки.
        blurred = cv2.GaussianBlur(search_gray, (3, 3), 0)
        binary = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            9,
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        expected_w = max(1, reference_box[2] - reference_box[0])
        expected_h = max(1, reference_box[3] - reference_box[1])

        best_box = None
        best_score = 0.0
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w < expected_w * 0.45 or h < expected_h * 0.45:
                continue
            if w > expected_w * 2.2 or h > expected_h * 2.8:
                continue
            if w * h < expected_w * expected_h * 0.30:
                continue

            score = self._score_candidate((x, y, w, h), reference_box, search_box)
            if score > best_score:
                best_score = score
                best_box = (sx1 + x, sy1 + y, sx1 + x + w, sy1 + y + h)

        if best_box is not None and best_score >= 0.62:
            status = "GOOD" if best_score >= 0.78 else "WARNING"
            logger.info(
                f"Local: рамка найдена, confidence={best_score:.2f}, box={best_box}"
            )
            return LocalAnalysisResult(
                status,
                best_box,
                best_score,
                "cell_contour",
                "Найдена рамка ячейки рядом с эталонной областью",
            )

        # Если контур нестабилен, не считаем анализ проваленным: расширенная зона
        # всё равно компенсирует небольшой сдвиг страницы и даёт OCR больше контекста.
        logger.info(
            f"Local: уверенная рамка не найдена (best={best_score:.2f}), "
            f"используется расширенная зона {search_box}"
        )
        return LocalAnalysisResult(
            "WARNING",
            search_box,
            best_score,
            "expanded_area",
            "Рамка ячейки не найдена уверенно; используется расширенная область",
        )

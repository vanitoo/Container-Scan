from __future__ import annotations

import cv2
import numpy as np
from PIL import ImageEnhance

from pdf_ocr_app.services.pdf_service import PDFService


class AlignedPDFService(PDFService):
    """PDF service that can crop OCR fields from an aligned page cache."""

    def __init__(self, state):
        super().__init__(state)
        if not hasattr(self.state, "aligned_page_images"):
            self.state.aligned_page_images = {}

    def set_aligned_page(self, page_index: int, image) -> None:
        self.state.aligned_page_images[page_index] = image.copy()

    def clear_aligned_pages(self) -> None:
        self.state.aligned_page_images.clear()

    def unload_pdf(self):
        result = super().unload_pdf()
        self.clear_aligned_pages()
        return result

    def extract_area_image(
        self,
        page_index: int,
        coords: tuple,
        dpi: int = 200,
        use_page_scale: bool = False,
    ):
        aligned = self.state.aligned_page_images.get(page_index)
        if aligned is None:
            return super().extract_area_image(page_index, coords, dpi=dpi, use_page_scale=use_page_scale)

        x_start, y_start, x_end, y_end = coords
        effective_scale = 500 / aligned.height if use_page_scale else self.state.last_scale_factor
        inverse_scale = 1 / effective_scale

        x0 = max(0, min(int(x_start * inverse_scale), aligned.width - 1))
        y0 = max(0, min(int(y_start * inverse_scale), aligned.height - 1))
        x1 = max(1, min(int(x_end * inverse_scale), aligned.width))
        y1 = max(1, min(int(y_end * inverse_scale), aligned.height))
        if x1 <= x0 or y1 <= y0:
            raise ValueError("Некорректные координаты aligned OCR-области")

        cropped = aligned.crop((x0, y0, x1, y1))
        cropped = ImageEnhance.Contrast(cropped).enhance(2.0)
        cropped = ImageEnhance.Sharpness(cropped).enhance(2.0)
        return cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2BGR)

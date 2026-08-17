# services/pdf_service.py
from __future__ import annotations

import tempfile
import time
from pathlib import Path
import tkinter.messagebox as messagebox

import fitz
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageTk

from pdf_ocr_app.models.state import AppState
from pdf_ocr_app.utils.logger import logger


class PDFService:
    def __init__(self, state: AppState):
        self.state = state

    def create_display_image(self) -> bool:
        """Создание изображения для отображения на canvas"""
        if not self.state.original_page_image:
            return False

        try:
            canvas_height = 500
            image_height = self.state.original_page_image.height
            scale_factor = canvas_height / image_height
            previous_scale = self.state.scale_factor
            if previous_scale != 1.0 and previous_scale != scale_factor:
                coordinate_ratio = scale_factor / previous_scale
                self.state.x_start = round(self.state.x_start * coordinate_ratio)
                self.state.y_start = round(self.state.y_start * coordinate_ratio)
                self.state.x_end = round(self.state.x_end * coordinate_ratio)
                self.state.y_end = round(self.state.y_end * coordinate_ratio)
            self.state.scale_factor = scale_factor
            self.state.last_scale_factor = scale_factor
            self.state.canvas_scale = scale_factor

            scaled_width = int(self.state.original_page_image.width * scale_factor)
            scaled_height = int(self.state.original_page_image.height * scale_factor)
            self.state.page_image = self.state.original_page_image.resize(
                (scaled_width, scaled_height), Image.LANCZOS
            )

            self.state.image_display = ImageTk.PhotoImage(image=self.state.page_image)
            return True

        except Exception as e:
            logger.error(f"Ошибка создания изображения для отображения: {e}")
            return False

    def next_page(self) -> bool:
        """Переход к следующей странице"""
        if self.state.pdf_doc and self.state.current_page < self.state.pdf_doc.page_count - 1:
            self.state.current_page += 1
            return self.load_page()
        return False

    def prev_page(self) -> bool:
        """Переход к предыдущей странице"""
        if self.state.pdf_doc and self.state.current_page > 0:
            self.state.current_page -= 1
            return self.load_page()
        return False

    def goto_page(self, page_num: int) -> bool:
        """Переход к конкретной странице"""
        if self.state.pdf_doc and 0 <= page_num < self.state.pdf_doc.page_count:
            self.state.current_page = page_num
            return self.load_page()
        return False

    def rotate_current_page(self, degrees: int) -> bool:
        """Rotate the current PDF page 90 degrees left or right."""
        if not self.state.pdf_doc or degrees not in (-90, 90):
            return False

        try:
            page = self.state.pdf_doc.load_page(self.state.current_page)
            page.set_rotation((page.rotation + degrees) % 360)
            direction = "вправо" if degrees > 0 else "влево"
            logger.info(f"Страница {self.state.current_page + 1} повернута {direction} на 90°")
            return self.load_page()
        except Exception as e:
            logger.error(f"Ошибка поворота страницы {self.state.current_page + 1}: {e}")
            return False

    @staticmethod
    def align_area_to_reference(reference_image, current_image, reference_box: tuple) -> dict | None:
        """Transfer a reference box using ORB feature matching and a homography."""
        reference_gray = cv2.cvtColor(np.asarray(reference_image), cv2.COLOR_RGB2GRAY)
        current_gray = cv2.cvtColor(np.asarray(current_image), cv2.COLOR_RGB2GRAY)

        max_width = 1100
        reference_scale = min(1.0, max_width / reference_gray.shape[1])
        current_scale = min(1.0, max_width / current_gray.shape[1])
        reference_small = cv2.resize(
            reference_gray,
            None,
            fx=reference_scale,
            fy=reference_scale,
            interpolation=cv2.INTER_AREA,
        )
        current_small = cv2.resize(
            current_gray,
            None,
            fx=current_scale,
            fy=current_scale,
            interpolation=cv2.INTER_AREA,
        )

        orb = cv2.ORB_create(nfeatures=4000)
        reference_points, reference_descriptors = orb.detectAndCompute(reference_small, None)
        current_points, current_descriptors = orb.detectAndCompute(current_small, None)
        if reference_descriptors is None or current_descriptors is None:
            return None

        matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(
            reference_descriptors,
            current_descriptors,
            k=2,
        )
        good_matches = [first for first, second in matches if first.distance < 0.72 * second.distance]
        if len(good_matches) < 20:
            return None

        source_points = np.float32(
            [reference_points[match.queryIdx].pt for match in good_matches]
        )
        target_points = np.float32(
            [current_points[match.trainIdx].pt for match in good_matches]
        )
        homography, inlier_mask = cv2.findHomography(
            source_points,
            target_points,
            cv2.RANSAC,
            4.0,
        )
        if homography is None or inlier_mask is None:
            return None

        inliers = int(inlier_mask.sum())
        if inliers < 12 or inliers / len(good_matches) < 0.25:
            return None

        x1, y1, x2, y2 = reference_box
        reference_corners = np.float32(
            [[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]]
        )
        reference_corners *= reference_scale
        transformed = cv2.perspectiveTransform(reference_corners, homography)
        transformed /= current_scale
        transformed = transformed.reshape(-1, 2)

        min_x, min_y = np.floor(transformed.min(axis=0)).astype(int)
        max_x, max_y = np.ceil(transformed.max(axis=0)).astype(int)
        image_width, image_height = current_image.size
        min_x = int(max(0, min(min_x, image_width - 1)))
        min_y = int(max(0, min(min_y, image_height - 1)))
        max_x = int(max(1, min(max_x, image_width)))
        max_y = int(max(1, min(max_y, image_height)))
        if max_x <= min_x or max_y <= min_y:
            return None

        return {
            "box": (min_x, min_y, max_x, max_y),
            "matches": len(good_matches),
            "inliers": inliers,
        }

    def load_page(self) -> bool:
        """Загрузка текущей страницы"""
        if not self.state.pdf_doc:
            return False

        try:
            current_page = max(0, min(self.state.current_page, self.state.pdf_doc.page_count - 1))
            self.state.original_page_image = self.render_page_image(current_page)

            logger.debug(f"Загружена страница {current_page + 1}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки страницы {self.state.current_page}: {e}")
            return False

    def render_page_image(self, page_index: int, dpi: int = 200) -> Image.Image:
        """Render a PDF page without changing the current-page state."""
        if not self.state.pdf_doc:
            raise ValueError("PDF document is not loaded")
        page = self.state.pdf_doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    def load_pdf(self, file_path: str) -> bool:
        """Загрузка PDF файла"""
        try:
            self.unload_pdf()
            self.state.pdf_doc = fitz.open(file_path)
            self.state.pdf_path = file_path
            self.state.is_temp_pdf = False
            self.state.current_page = 0
            self.state.total_pages = self.state.pdf_doc.page_count
            return True
        except Exception as e:
            logger.error(f"Ошибка загрузки PDF: {e}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить PDF: {e}")
            return False

    def unload_pdf(self):
        """Закрытие PDF документа"""
        try:
            if self.state.pdf_doc:
                self.state.pdf_doc.close()
                self.state.pdf_doc = None

            if self.state.is_temp_pdf and self.state.pdf_path:
                try:
                    path = Path(self.state.pdf_path)
                    if path.exists():
                        path.unlink()
                        logger.info(f"Удалён временный PDF: {path}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный PDF '{self.state.pdf_path}': {e}")

            self.state.pdf_doc = None
            self.state.pdf_path = None
            self.state.current_page = 0
            self.state.page_image = None
            self.state.original_page_image = None
            self.state.image_display = None
            self.state.layout_reference_image = None
            self.state.layout_reference_box = None
            self.state.selected_areas = []
            self.state.total_pages = 0
            self.state.scale_factor = 1.0
            self.state.last_scale_factor = 1.0

        except Exception as e:
            logger.warning(f"Не удалось закрыть PDF: {e}")
            return False

    def process_multiple_pdfs(self, file_paths: list) -> bool:
        """Обработка нескольких PDF файлов"""
        try:
            self.unload_pdf()
            merged_doc = fitz.open()

            for file_path in file_paths:
                try:
                    doc = fitz.open(file_path)
                    page_count_before = merged_doc.page_count
                    merged_doc.insert_pdf(doc)
                    page_count_after = merged_doc.page_count
                    added_pages = page_count_after - page_count_before
                    doc.close()
                    logger.info(f"Добавлен файл: {Path(file_path).name} ({added_pages} стр.)")
                except Exception as e:
                    logger.error(f"Ошибка при обработке файла {file_path}: {e}")
                    continue

            if merged_doc.page_count == 0:
                messagebox.showerror("Ошибка", "Не удалось загрузить ни одного PDF файла")
                merged_doc.close()
                return False

            try:
                base_dir = Path(file_paths[0]).parent if file_paths else Path(tempfile.gettempdir())
                temp_pdf = base_dir / f"merged_pdf_{int(time.time())}.pdf"
                merged_doc.save(temp_pdf)
            except Exception:
                fallback_dir = Path(tempfile.gettempdir())
                temp_pdf = fallback_dir / f"merged_pdf_{int(time.time())}.pdf"
                merged_doc.save(temp_pdf)
            finally:
                merged_doc.close()

            self.state.pdf_doc = fitz.open(temp_pdf)
            self.state.pdf_path = str(temp_pdf)
            self.state.is_temp_pdf = True
            self.state.current_page = 0
            self.state.total_pages = self.state.pdf_doc.page_count

            return True

        except Exception as e:
            logger.error(f"Ошибка при обработке нескольких PDF: {e}")
            messagebox.showerror("Ошибка", f"Не удалось объединить PDF файлы: {e}")
            return False

    def extract_area_image(
        self,
        page_index: int,
        coords: tuple,
        dpi: int = 200,
        use_page_scale: bool = False,
    ):
        """Извлечение области изображения из PDF"""
        x_start, y_start, x_end, y_end = coords

        if x_end <= x_start or y_end <= y_start:
            raise ValueError("Некорректные координаты области выделения")

        page = self.state.pdf_doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi)
        page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Manual recognition uses the scale calculated when the current page is
        # displayed. Mass recognition has no displayed page, so calculate the
        # same fit-to-500px scale independently for every rendered page.
        effective_scale = (
            500 / page_image.height
            if use_page_scale
            else self.state.last_scale_factor
        )
        inverse_scale = 1 / effective_scale

        if self.state.debug_mode:
            page_scale = 500 / page_image.height
            logger.debug(
                f"Массовый OCR — страница {page_index + 1}: "
                f"PDF={page.rect.width:.2f}x{page.rect.height:.2f} pt, dpi={dpi}, "
                f"render={page_image.width}x{page_image.height} px, "
                f"height={page_image.height} px, "
                f"display target height=500 px, "
                f"единый масштаб={self.state.last_scale_factor:.8f}, "
                f"масштаб листа={page_scale:.8f}, "
                f"выбранный масштаб={effective_scale:.8f}, "
                f"inverse={inverse_scale:.8f}, "
                f"режим={'по листу' if use_page_scale else 'единый'}, "
                f"canvas coords={coords}"
            )

        x0 = int(x_start * inverse_scale)
        y0 = int(y_start * inverse_scale)
        x1 = int(x_end * inverse_scale)
        y1 = int(y_end * inverse_scale)

        x0 = max(0, min(x0, page_image.width - 1))
        y0 = max(0, min(y0, page_image.height - 1))
        x1 = max(1, min(x1, page_image.width))
        y1 = max(1, min(y1, page_image.height))

        if x1 <= x0 or y1 <= y0:
            raise ValueError("Некорректные координаты после масштабирования")

        if self.state.debug_mode:
            logger.debug(
                f"Массовый OCR — страница {page_index + 1}: "
                f"crop=({x0},{y0})-({x1},{y1}), "
                f"crop size={x1 - x0}x{y1 - y0} px"
            )

        cropped = page_image.crop((x0, y0, x1, y1))
        if cropped.size[0] == 0 or cropped.size[1] == 0:
            raise ValueError("Выделенная область имеет нулевой размер")

        enhancer = ImageEnhance.Contrast(cropped)
        cropped = enhancer.enhance(2.0)

        enhancer = ImageEnhance.Sharpness(cropped)
        cropped = enhancer.enhance(2.0)

        return cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2BGR)

    def extract_area_image_new(self, page_index: int, coords: tuple, dpi: int = 200):
        """Извлечение области изображения из PDF с учётом нормализованного выделения."""
        page = self.state.pdf_doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi)
        page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        x_start, y_start, x_end, y_end = coords
        x1n = y1n = x2n = y2n = None
        norm = getattr(self.state, "selection_rect_norm", None)
        if norm:
            try:
                x1n, y1n, x2n, y2n = norm
            except Exception:
                x1n = y1n = x2n = y2n = None

        if x1n is None:
            disp_img = getattr(self.state, "page_image", None)
            if disp_img is not None and disp_img.width and disp_img.height:
                w, h = disp_img.width, disp_img.height
                x1n = max(0.0, min(1.0, x_start / w))
                y1n = max(0.0, min(1.0, y_start / h))
                x2n = max(0.0, min(1.0, x_end / w))
                y2n = max(0.0, min(1.0, y_end / h))

        if x1n is not None:
            x_start = int(round(x1n * page_image.width))
            y_start = int(round(y1n * page_image.height))
            x_end = int(round(x2n * page_image.width))
            y_end = int(round(y2n * page_image.height))

        if x_end < x_start:
            x_start, x_end = x_end, x_start
        if y_end < y_start:
            y_start, y_end = y_end, y_start

        x0 = max(0, min(int(x_start), page_image.width - 1))
        y0 = max(0, min(int(y_start), page_image.height - 1))
        x1 = max(1, min(int(x_end), page_image.width))
        y1 = max(1, min(int(y_end), page_image.height))

        if x1 <= x0 or y1 <= y0:
            raise ValueError("Некорректные координаты области выделения")

        cropped = page_image.crop((x0, y0, x1, y1))
        if cropped.size[0] == 0 or cropped.size[1] == 0:
            raise ValueError("Выделенная область имеет нулевой размер")

        enhancer = ImageEnhance.Contrast(cropped)
        cropped = enhancer.enhance(2.0)

        enhancer = ImageEnhance.Sharpness(cropped)
        cropped = enhancer.enhance(2.0)

        return cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2BGR)

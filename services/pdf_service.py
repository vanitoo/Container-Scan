# services/pdf_service.py
from __future__ import annotations
import tempfile
import time
import fitz
from PIL import Image, ImageTk
import tkinter.messagebox as messagebox

from models.state import AppState
from utils.logger import logger
from config import DEFAULT_COORDINATES
from pathlib import Path


class PDFService:
    def __init__(self, state: AppState):
        self.state = state

    def create_display_image(self) -> bool:
        """Создание изображения для отображения на canvas"""
        if not self.state.original_page_image:
            return False

        try:
            # Масштабирование для отображения
            canvas_height = 500
            image_height = self.state.original_page_image.height
            scale_factor = canvas_height / image_height
            self.state.scale_factor = scale_factor
            self.state.last_scale_factor = scale_factor

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


    def load_page(self) -> bool:
        """Загрузка текущей страницы - упрощенная версия"""
        if not self.state.pdf_doc:
            return False

        try:
            current_page = max(0, min(self.state.current_page, self.state.pdf_doc.page_count - 1))
            page = self.state.pdf_doc.load_page(current_page)

            # Простое получение изображения без сложной логики
            pix = page.get_pixmap(dpi=200)  # Уменьшаем DPI для производительности
            self.state.original_page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            logger.debug(f"Загружена страница {current_page + 1}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки страницы {self.state.current_page}: {e}")
            return False

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

            # Удалить временный объединённый PDF (если он наш)
            if self.state.is_temp_pdf and self.state.pdf_path:
                try:
                    p = Path(self.state.pdf_path)
                    if p.exists():
                        p.unlink()
                        logger.info(f"Удалён временный PDF: {p}")
                except Exception as e:
                    # Не мешаем работе, просто предупредим
                    logger.warning(f"Не удалось удалить временный PDF '{self.state.pdf_path}': {e}")


            # Сброс состояния
            self.state.pdf_doc = None
            self.state.pdf_path = None
            self.state.current_page = 0
            self.state.page_image = None
            self.state.original_page_image = None
            self.state.image_display = None
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

            # Сохранение временного файла
            # temp_dir = Path(tempfile.gettempdir())
            # temp_pdf = temp_dir / f"merged_pdf_{int(time.time())}.pdf"
            # merged_doc.save(temp_pdf)
            # merged_doc.close()
            try:
                base_dir = Path(file_paths[0]).parent if file_paths else Path(tempfile.gettempdir())
                temp_pdf = base_dir / f"merged_pdf_{int(time.time())}.pdf"
                merged_doc.save(temp_pdf)
            except Exception:
                # fallback: если нет прав на запись в base_dir — уходим в системный temp
                fallback_dir = Path(tempfile.gettempdir())
                temp_pdf = fallback_dir / f"merged_pdf_{int(time.time())}.pdf"
                merged_doc.save(temp_pdf)
            finally:
                merged_doc.close()

            # Загрузка объединенного документа
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

    def extract_area_image(self, page_index: int, coords: tuple, dpi: int = 200):
        """Извлечение области изображения из PDF"""
        import cv2
        import numpy as np
        from PIL import ImageEnhance

        x_start, y_start, x_end, y_end = coords

        if x_end <= x_start or y_end <= y_start:
            raise ValueError("Некорректные координаты области выделения")

        page = self.state.pdf_doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi)
        page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Пересчет координат
        inverse_scale = 1 / self.state.last_scale_factor

        # canvas_height = 500  # то же значение, что используется при отображении
        # image_height = page_image.height
        # scale_factor = canvas_height / image_height if image_height else 1.0
        # inverse_scale = 1.0 / scale_factor


        x0 = int(x_start * inverse_scale)
        y0 = int(y_start * inverse_scale)
        x1 = int(x_end * inverse_scale)
        y1 = int(y_end * inverse_scale)

        # Проверка границ
        x0 = max(0, min(x0, page_image.width - 1))
        y0 = max(0, min(y0, page_image.height - 1))
        x1 = max(1, min(x1, page_image.width))
        y1 = max(1, min(y1, page_image.height))

        if x1 <= x0 or y1 <= y0:
            raise ValueError("Некорректные координаты после масштабирования")

        cropped = page_image.crop((x0, y0, x1, y1))
        if cropped.size[0] == 0 or cropped.size[1] == 0:
            raise ValueError("Выделенная область имеет нулевой размер")

        # Увеличение контрастности
        enhancer = ImageEnhance.Contrast(cropped)
        cropped = enhancer.enhance(2.0)

        # Повышение резкости
        enhancer = ImageEnhance.Sharpness(cropped)
        cropped = enhancer.enhance(2.0)

        return cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2BGR)

    def extract_area_image_new(self, page_index: int, coords: tuple, dpi: int = 200):
        """Извлечение области изображения из PDF с учётом нормализованного выделения."""
        import cv2
        import numpy as np
        from PIL import Image, ImageEnhance  # Image у вас уже импортирован выше; оставил для замкнутости

        # Рендерим страницу в пикселях при заданном dpi
        page = self.state.pdf_doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi)
        page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Входные координаты (как есть)
        x_start, y_start, x_end, y_end = coords

        # 1) Пытаемся взять нормализованные координаты из состояния
        x1n = y1n = x2n = y2n = None
        norm = getattr(self.state, "selection_rect_norm", None)
        if norm:
            try:
                x1n, y1n, x2n, y2n = norm
            except Exception:
                x1n = y1n = x2n = y2n = None

        # 2) Если нормализации нет — считаем её из экранных coords и размеров отображаемого изображения
        if x1n is None:
            disp_img = getattr(self.state, "page_image", None)
            if disp_img is not None and disp_img.width and disp_img.height:
                w, h = disp_img.width, disp_img.height
                x1n = max(0.0, min(1.0, x_start / w))
                y1n = max(0.0, min(1.0, y_start / h))
                x2n = max(0.0, min(1.0, x_end / w))
                y2n = max(0.0, min(1.0, y_end / h))

        # 3) Если получили нормализованные — пересчитываем в пиксели ТЕКУЩЕЙ страницы
        if x1n is not None:
            x_start = int(round(x1n * page_image.width))
            y_start = int(round(y1n * page_image.height))
            x_end = int(round(x2n * page_image.width))
            y_end = int(round(y2n * page_image.height))

        # Нормализация порядка и клип в границы изображения
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

        # Препроцессинг для OCR (контраст/резкость)
        enhancer = ImageEnhance.Contrast(cropped)
        cropped = enhancer.enhance(2.0)

        enhancer = ImageEnhance.Sharpness(cropped)
        cropped = enhancer.enhance(2.0)

        # Возвращаем как BGR (для OpenCV/pytesseract)
        return cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2BGR)


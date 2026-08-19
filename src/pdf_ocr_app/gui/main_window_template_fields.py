from __future__ import annotations

import threading
from tkinter import messagebox

from pdf_ocr_app.gui.main_window_alignment import MainWindow as AlignmentMainWindow
from pdf_ocr_app.utils.logger import logger


class MainWindow(AlignmentMainWindow):
    """Analysis1 variant driven by fixed SMGS template fields."""

    def analyze_layout_v1_template(self):
        """Map the fixed container field from SMGS-01 onto the current scan."""
        if not self.state.pdf_doc or self.state.original_page_image is None:
            messagebox.showwarning("Анализ1", "Сначала выберите PDF-файл.")
            return

        try:
            reference_image = self.app.template_service.load_smgs_01()
            reference_box = self.app.template_service.get_smgs_01_field_box(
                "container_number",
                reference_image,
            )
        except Exception as exc:
            logger.error(
                f"Анализ1: не удалось загрузить шаблон/fields.json SMGS-01: {exc}",
                exc_info=True,
            )
            messagebox.showerror(
                "Анализ1",
                f"Не удалось загрузить шаблон или fields.json SMGS-01:\n{exc}",
            )
            return

        self.btn_analyze_layout.config(state="disabled")
        self.components["status"].update_status(
            msg="Анализ1: поиск ячейки 15 и строки контейнера по шаблону SMGS-01..."
        )

        page_image = self.state.original_page_image.copy()
        logger.info(
            "Анализ1: ручная красная область игнорируется; "
            f"используется container_number из fields.json: {reference_box}"
        )
        threading.Thread(
            target=self._analyze1_template_worker,
            args=(reference_image, page_image, reference_box),
            daemon=True,
        ).start()

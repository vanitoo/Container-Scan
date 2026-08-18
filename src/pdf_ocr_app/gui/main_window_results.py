from __future__ import annotations

from pdf_ocr_app.gui.main_window import MainWindow as BaseMainWindow


class MainWindow(BaseMainWindow):
    """Main window with per-page OCR result display during navigation."""

    def _get_recognition_result_for_page(self, page_num: int):
        """Return the latest stored OCR result for a zero-based page index."""
        target_page = page_num + 1
        for result in reversed(self.state.recognition_results):
            if result.get("page") == target_page:
                return result
        return None

    def _show_recognition_result_for_page(self, page_num: int) -> None:
        """Refresh the OCR details panel for the selected page."""
        result = self._get_recognition_result_for_page(page_num)
        self.components["canvas"].show_recognition_result(result)

    def prev_page(self):
        super().prev_page()
        self._show_recognition_result_for_page(self.state.current_page)

    def next_page(self):
        super().next_page()
        self._show_recognition_result_for_page(self.state.current_page)

    def goto_page_from_table(self, page_num):
        # Base implementation skips reloading when the selected row is already
        # the current page. The OCR panel still needs to be refreshed in that case.
        if self.state.current_page == page_num:
            self._show_recognition_result_for_page(page_num)
            return

        super().goto_page_from_table(page_num)
        self._show_recognition_result_for_page(page_num)

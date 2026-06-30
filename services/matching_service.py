# services/matching_service.py
from __future__ import annotations

from models.state import AppState
from utils.logger import logger


class MatchingService:
    def __init__(self, state: AppState, ocr_service):
        self.state = state
        self.ocr_service = ocr_service

    def match_entries(self, table_entries: list[dict], expected_containers: list[str]) -> list[dict]:
        """Сопоставление распознанных контейнеров с ожидаемыми значениями."""
        unique_expected = []
        for expected in expected_containers:
            if expected and expected not in unique_expected:
                unique_expected.append(expected)

        if not unique_expected:
            logger.warning("Нет данных для сопоставления в загруженном Excel файле")
            return []

        results = []
        for entry in table_entries:
            recognized = (entry.get("recognized") or "").strip()
            if not recognized:
                continue

            best_match = ""
            best_score = 0.0

            for expected in unique_expected:
                score = self.ocr_service.is_similar_ratio(recognized, expected)
                if score > best_score:
                    best_score = score
                    best_match = expected

            if best_score == 1.0:
                tag = "exact_match"
            elif best_score > 0:
                tag = "partial_match"
            else:
                tag = "no_match"

            results.append(
                {
                    "item_id": entry.get("item_id"),
                    "best_match": best_match,
                    "best_score": best_score,
                    "tag": tag,
                }
            )

        logger.info("Сопоставление завершено")
        return results

    def match_with_expected(self, tree_widget) -> bool:
        """Совместимая обёртка для старого GUI-кода."""
        expected_containers = [container for _, container in self.state.all_excel_records if container]
        match_results = self.match_entries(self.state.table_entries, expected_containers)

        if not match_results:
            return False

        for result in match_results:
            item_id = result.get("item_id")
            if not item_id:
                continue

            values = list(tree_widget.item(item_id, "values"))
            while len(values) < 6:
                values.append("")

            values[4] = result["best_match"]
            values[5] = f'{result["best_score"]:.2f}'
            tree_widget.item(item_id, values=values)

            tree_widget.tag_configure("exact_match", background="#a8e6a8")
            tree_widget.tag_configure("partial_match", background="#fff8a8")
            tree_widget.tag_configure("no_match", background="#ffaaaa")
            tree_widget.item(item_id, tags=(result["tag"],))

        return True

    def find_invoice_by_expected(self, expected_value: str) -> str:
        """Поиск номера накладной по ожидаемому контейнеру"""
        if not expected_value:
            return ""

        for xls_id, container in self.state.all_excel_records:
            if container and container.strip() == expected_value.strip():
                return xls_id

        return ""

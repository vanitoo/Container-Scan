# services/matching_service.py
from __future__ import annotations
from models.state import AppState
from utils.logger import logger


class MatchingService:
    def __init__(self, state: AppState, ocr_service):
        self.state = state
        self.ocr_service = ocr_service

    def match_with_expected(self, tree_widget) -> bool:
        """Сопоставление распознанных контейнеров с ожидаемыми"""
        expected_containers = []
        for xls_id, container in self.state.all_excel_records:
            if container and container not in expected_containers:
                expected_containers.append(container)

        if not expected_containers:
            logger.warning("Нет данных для сопоставления в загруженном Excel файле")
            return False

        for entry in self.state.table_entries:
            recognized = entry.get("recognized", "")
            if not recognized:
                continue

            best_match = ""
            best_score = 0.0

            for expected in expected_containers:
                if not expected:
                    continue
                score = self.ocr_service.is_similar_ratio(recognized, expected)
                if score > best_score:
                    best_score = score
                    best_match = expected

            # Обновление строки в таблице
            values = list(tree_widget.item(entry["item_id"], "values"))
            values[4] = best_match  # Совпадение
            values[5] = f"{best_score:.2f}"  # Коэффициент
            tree_widget.item(entry["item_id"], values=values)

            # Обновление цвета строки
            if best_score == 1.0:
                tree_widget.tag_configure("exact_match", background="#a8e6a8")
                tree_widget.item(entry["item_id"], tags=("exact_match",))
            elif best_score > 0:
                tree_widget.tag_configure("partial_match", background="#fff8a8")
                tree_widget.item(entry["item_id"], tags=("partial_match",))
            else:
                tree_widget.tag_configure("no_match", background="#ffaaaa")
                tree_widget.item(entry["item_id"], tags=("no_match",))

        logger.info("Сопоставление завершено")
        return True

    def find_invoice_by_expected(self, expected_value: str) -> str:
        """Поиск номера накладной по ожидаемому контейнеру"""
        if not expected_value:
            return ""

        for xls_id, container in self.state.all_excel_records:
            if container and container.strip() == expected_value.strip():
                return xls_id

        return ""
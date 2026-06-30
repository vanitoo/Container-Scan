# services/excel_service.py
from __future__ import annotations

import csv
from pathlib import Path
import tkinter.messagebox as messagebox

import openpyxl

from models.state import AppState
from utils.logger import logger


class ExcelService:
    def __init__(self, state: AppState):
        self.state = state

    def load_registry(self, file_path: str) -> bool:
        """Загрузка данных из Excel или CSV файла"""
        try:
            suffix = Path(file_path).suffix.lower()

            if suffix == ".xlsx":
                records = self._load_excel(file_path)
            elif suffix == ".csv":
                records = self._load_csv(file_path)
            else:
                messagebox.showerror("Ошибка", f"Неподдерживаемый формат: {suffix}")
                return False

            self.state.all_excel_records = records
            self._update_table_from_records(records)

            logger.info(f"Загружено {len(records)} записей из {file_path}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при загрузке реестра: {e}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить реестр: {e}")
            return False

    def _update_table_from_records(self, records):
        """Обновление таблицы данными из загруженных записей"""
        updated_rows = min(len(records), len(self.state.table_entries))
        for i in range(updated_rows):
            xls_id, code = records[i]

            self.state.table_entries[i]["code"] = code
            self.state.table_entries[i]["xls_id"] = xls_id

            item_id = self.state.table_entries[i]["item_id"]
            current_values = list(self.state.gui.tree.item(item_id, "values"))

            # Гарантируем длину 6: [№, expected, invoice, recognized, match, score]
            while len(current_values) < 6:
                current_values.append("")

            current_values[1] = code
            current_values[2] = xls_id

            self.state.gui.tree.item(item_id, values=tuple(current_values))

    def _load_excel(self, file_path: str) -> list:
        """Загрузка данных из Excel файла"""
        records = []
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active

        logger.info(f"Чтение данных из Excel файла: {file_path}")

        for row in sheet.iter_rows(min_row=5):
            xls_id = ""
            container = ""

            # Колонка 3 (индекс 2) - номер накладной
            if len(row) > 2 and row[2].value is not None:
                xls_id = str(row[2].value).strip()

            # Колонка 4 (индекс 3) - контейнер
            if len(row) > 3:
                cell = row[3].value
                if cell is not None:
                    s = str(cell)
                    container = s.split("/")[-1].strip() if "/" in s else s.strip()

            records.append((xls_id, container))

        return records

    def _load_csv(self, file_path: str) -> list:
        """Загрузка данных из CSV файла"""
        records = []

        logger.info(f"Чтение данных из CSV файла: {file_path}")

        with Path(file_path).open(encoding="utf-8") as f:
            reader = csv.reader(f)
            for idx, row in enumerate(reader):
                if idx < 3:
                    continue

                xls_id = row[2].strip() if len(row) > 2 and row[2] is not None else ""
                cell = row[3] if len(row) > 3 else ""

                if cell:
                    cell = str(cell)
                    container = cell.split("/")[-1].strip() if "/" in cell else cell.strip()
                else:
                    container = ""

                records.append((xls_id, container))

        return records

    def get_expected_containers(self) -> list:
        """Получение списка ожидаемых контейнеров"""
        return [container for _, container in self.state.all_excel_records if container]

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pdf_ocr_app.services.excel_service import ExcelService
from pdf_ocr_app.utils.updater import AutoUpdater


def test_csv_registry_skips_headers_and_normalizes_container(tmp_path) -> None:
    registry = tmp_path / "registry.csv"
    registry.write_text(
        "header\nheader\nheader\n,,INV-1,prefix/MSCU1234567\n,,INV-2,TGHU7654321\n",
        encoding="utf-8",
    )
    service = ExcelService(SimpleNamespace())

    assert service.read_registry(str(registry)) == [
        ("INV-1", "MSCU1234567"),
        ("INV-2", "TGHU7654321"),
    ]


def test_registry_rejects_unsupported_file_format(tmp_path) -> None:
    registry = tmp_path / "registry.txt"
    registry.write_text("data", encoding="utf-8")

    with pytest.raises(ValueError):
        ExcelService(SimpleNamespace()).read_registry(str(registry))


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("2.0.5", "2.0.6", -1),
        ("2.0.6", "2.0.6", 0),
        ("2.1.0", "2.0.9", 1),
    ],
)
def test_compare_versions(left: str, right: str, expected: int) -> None:
    assert AutoUpdater.compare_versions(left, right) == expected

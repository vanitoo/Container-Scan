from __future__ import annotations

import pytest

from pdf_ocr_app.services.ocr_service import OCRService


@pytest.fixture
def ocr_service() -> OCRService:
    # Formatting and similarity do not need initialized OCR backends or AppState.
    return OCRService.__new__(OCRService)


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("MSCU1234567", "MSCU1234567"),
        ("mscu 1234567", "MSCU1234567"),
        ("text MSCU-1234567 other", "MSCU1234567"),
        ("MSCU123456X", "MSCU123456@"),
        ("M5CU1234567", "M@CU1234567"),
    ],
)
def test_format_extracted_text(ocr_service: OCRService, raw_text: str, expected: str) -> None:
    assert ocr_service.format_extracted_text(raw_text, page_num=1) == expected


def test_similarity_is_exact_for_equal_container_numbers(ocr_service: OCRService) -> None:
    assert ocr_service.is_similar_ratio("MSCU1234567", "MSCU1234567") == 1.0


def test_similarity_decreases_when_character_differs(ocr_service: OCRService) -> None:
    score = ocr_service.is_similar_ratio("MSCU1234567", "MSCU1234568")

    assert 0.0 < score < 1.0

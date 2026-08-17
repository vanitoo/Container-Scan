from __future__ import annotations

from types import SimpleNamespace

from pdf_ocr_app.services.matching_service import MatchingService
from pdf_ocr_app.services.ocr_service import OCRService


def make_service(records=()) -> MatchingService:
    state = SimpleNamespace(all_excel_records=list(records))
    return MatchingService(state, OCRService.__new__(OCRService))


def test_match_entries_selects_exact_and_closest_values() -> None:
    service = make_service()
    entries = [
        {"item_id": "page-1", "recognized": "MSCU1234567"},
        {"item_id": "page-2", "recognized": "TGHU765432X"},
        {"item_id": "page-3", "recognized": ""},
    ]

    results = service.match_entries(entries, ["MSCU1234567", "TGHU7654321"])

    assert results[0] == {
        "item_id": "page-1",
        "best_match": "MSCU1234567",
        "best_score": 1.0,
        "tag": "exact_match",
    }
    assert results[1]["best_match"] == "TGHU7654321"
    assert results[1]["tag"] == "partial_match"
    assert len(results) == 2


def test_match_entries_ignores_duplicate_expected_values() -> None:
    service = make_service()

    results = service.match_entries(
        [{"item_id": "page-1", "recognized": "MSCU1234567"}],
        ["MSCU1234567", "MSCU1234567"],
    )

    assert len(results) == 1
    assert results[0]["tag"] == "exact_match"


def test_match_entries_returns_empty_without_registry_values() -> None:
    service = make_service()

    assert service.match_entries([{"recognized": "MSCU1234567"}], []) == []


def test_find_invoice_by_expected_trims_registry_values() -> None:
    service = make_service([("INV-42", " MSCU1234567 ")])

    assert service.find_invoice_by_expected("MSCU1234567") == "INV-42"
    assert service.find_invoice_by_expected("UNKNOWN") == ""

from __future__ import annotations

import importlib.util

from .base import EngineInitResult, OCRBackend


class EasyOCREngine(OCRBackend):
    name = "EasyOCR"
    module_name = "easyocr"
    install_hint = "Установить EasyOCR можно командой: pip install easyocr"

    def is_installed(self) -> bool:
        return importlib.util.find_spec(self.module_name) is not None

    def initialize(self) -> EngineInitResult:
        if not self.is_installed():
            return EngineInitResult(False, self.name, "EasyOCR не установлен.", self.install_hint)

        return EngineInitResult(
            False,
            self.name,
            "EasyOCR установлен, но на этом этапе ещё не подключён.",
            self.install_hint,
        )

    def recognize(self, image) -> str:
        raise NotImplementedError("EasyOCR пока не подключён.")

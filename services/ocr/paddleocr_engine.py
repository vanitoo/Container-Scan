from __future__ import annotations

import importlib.util

from .base import EngineInitResult, OCRBackend


class PaddleOCREngine(OCRBackend):
    name = "PaddleOCR"
    module_name = "paddleocr"
    install_hint = "Установить PaddleOCR можно командой: pip install paddleocr"

    def is_installed(self) -> bool:
        return importlib.util.find_spec(self.module_name) is not None

    def initialize(self) -> EngineInitResult:
        if not self.is_installed():
            return EngineInitResult(False, self.name, "PaddleOCR не установлен.", self.install_hint)

        return EngineInitResult(
            False,
            self.name,
            "PaddleOCR установлен, но на этом этапе ещё не подключён.",
            self.install_hint,
        )

    def recognize(self, image) -> str:
        raise NotImplementedError("PaddleOCR пока не подключён.")

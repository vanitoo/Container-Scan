from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EngineInitResult:
    ok: bool
    engine: str
    message: str
    install_hint: str | None = None


class OCRBackend(ABC):
    name: str = ""
    install_hint: str | None = None

    @abstractmethod
    def is_installed(self) -> bool:
        """Проверка наличия backend-зависимости."""

    @abstractmethod
    def initialize(self) -> EngineInitResult:
        """Инициализация backend."""

    @abstractmethod
    def recognize(self, image) -> str:
        """Распознавание текста."""

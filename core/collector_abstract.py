"""Абстракции ядра. Linux-реализация позже подсунится без правок потребителей."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Sample:
    fps: float | None = None
    ping_ms: float | None = None
    loss_pct: float | None = None
    cpu_temp: float | None = None
    cpu_pct: float | None = None
    gpu_temp: float | None = None
    gpu_pct: float | None = None
    vram_used_mb: float | None = None
    ram_pct: float | None = None
    frame_ms: float | None = None


class ICollector(ABC):
    @abstractmethod
    def sample(self) -> Sample:
        ...


class IInputTester(ABC):
    """СТАБ под будущий модуль для osu!: polling rate, лаг, дребезг."""
    @abstractmethod
    def start(self) -> None:
        ...


class IOptimizer(ABC):
    """СТАБ под будущий модуль профилей: priority/affinity/kill."""
    @abstractmethod
    def apply_profile(self, process_name: str, profile: dict) -> None:
        ...

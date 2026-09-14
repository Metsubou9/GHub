from core.collector_abstract import IOptimizer
from modules.optimizer.optimizer_win import OptimizerWin


def get_optimizer() -> IOptimizer:
    return OptimizerWin()


class OptimizerStub(IOptimizer):
    """Задел под профили. Реализация следующим этапом."""
    def apply_profile(self, process_name: str, profile: dict) -> None:
        raise NotImplementedError("optimizer будет реализован после MVP monitoring")

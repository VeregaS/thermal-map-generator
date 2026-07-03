import array
from typing import NamedTuple, Optional
from dataclasses import dataclass

class BmpData(NamedTuple):
    """
    Контейнер для хранения исходных данных теплового снимка и калибровочных коэффициентов.
    """
    width: int
    height: int
    raw_data: array.array
    m_coef: float = 0.0003342
    a_coef: float = 0.1

class TemperatureStats(NamedTuple):
    """
    Статистические метрики, рассчитанные для матрицы температур.
    """
    min_t: float
    max_t: float
    avg_t: float
    median_t: float
    std_dev: float
    valid_pixels: int

class AnalysisResult(NamedTuple):
    """
    Результат обработки снимка, содержащий вычисленные температуры и их статистику.
    """
    width: int
    height: int
    temperatures: array.array
    stats: TemperatureStats

@dataclass
class ThermalSessionModel:
    """
    Модель состояния текущей рабочей сессии приложения.
    Хранит загруженные данные, результаты анализа и текущие настройки визуализации.
    """
    bmp_data: Optional[BmpData] = None
    analysis_result: Optional[AnalysisResult] = None
    min_t: float = 0.0
    max_t: float = 0.0
    palette: str = "JET"
import array
from typing import NamedTuple, Optional

class BmpData(NamedTuple):
    width: int
    height: int
    raw_data: array.array
    m_coef: float = 0.0003342
    a_coef: float = 0.1

class TemperatureStats(NamedTuple):
    min_t: float
    max_t: float
    avg_t: float
    median_t: float
    std_dev: float
    valid_pixels: int

class AnalysisResult(NamedTuple):
    width: int
    height: int
    temperatures: array.array
    stats: TemperatureStats

class ThermalSessionModel:
    def __init__(self) -> None:
        self.bmp_data: Optional[BmpData] = None
        self.analysis_result: Optional[AnalysisResult] = None
        self.min_t: float = 0.0
        self.max_t: float = 0.0
        self.palette: str = "JET"
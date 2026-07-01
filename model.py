from typing import NamedTuple, List

class BmpData(NamedTuple):
    """Структура для хранения исходных метаданных и матрицы яркости BMP."""
    width: int
    height: int
    raw_dn_matrix: List[List[int]]

class TemperatureStats(NamedTuple):
    """Структура для хранения агрегированных статистических показателей."""
    min_t: float
    max_t: float
    avg_t: float

class AnalysisResult(NamedTuple):
    """Итоговая структура, содержащая геометрию, матрицу температур и статистику."""
    width: int
    height: int
    temp_matrix_c: List[List[float]]
    stats: TemperatureStats

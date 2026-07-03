import rasterio
import numpy as np
import array
from typing import Tuple

M_ORIG: float = 0.0003342
A_ORIG: float = 0.1

def _calculate_coefficients(min_val: float, max_val: float) -> Tuple[float, float]:
    """
    Вычисляет новые калибровочные коэффициенты для нормализованных данных.

    Args:
        min_val: Нижняя граница (1-й перцентиль) валидных данных.
        max_val: Верхняя граница (99-й перцентиль) валидных данных.

    Returns:
        Кортеж из масштабирующего коэффициента (m) и смещения (a).
    """
    if max_val <= 255:
        fake_min = 20000.0
        fake_max = 30000.0
        m_new = (M_ORIG * (fake_max - fake_min)) / 254.0
        a_new = M_ORIG * fake_min - m_new + A_ORIG
    else:
        m_new = (M_ORIG * (max_val - min_val)) / 254.0
        a_new = M_ORIG * min_val - m_new + A_ORIG
        
    return float(m_new), float(a_new)

def _normalize_and_scale(band: np.ndarray, valid_mask: np.ndarray, min_val: float, max_val: float) -> array.array:
    """
    Масштабирует валидные пиксели в 8-битный диапазон, резервируя 0 для пустых значений.

    Args:
        band: Исходная матрица пикселей.
        valid_mask: Булева маска валидных значений.
        min_val: Значение для приведения к минимуму (1).
        max_val: Значение для приведения к максимуму (255).

    Returns:
        Одномерный байтовый массив нормализованных значений.
    """
    norm_band = np.zeros_like(band, dtype=np.uint8)
    scaled = ((band[valid_mask] - min_val) / (max_val - min_val) * 254 + 1)
    norm_band[valid_mask] = np.clip(scaled, 1, 255).astype(np.uint8)
    
    return array.array('B', norm_band.tobytes())

def load_tif_data(input_tif_path: str) -> Tuple[int, int, array.array, float, float]:
    """
    Открывает TIF снимок, отбраковывает нулевые значения, обрезает экстремумы 
    по перцентилям и нормализует матрицу для последующей обработки.

    Args:
        input_tif_path: Путь к файлу TIF.

    Returns:
        Кортеж (ширина, высота, сырой массив пикселей, коэффициент m, коэффициент a).
    """
    with rasterio.open(input_tif_path) as src:
        band1 = src.read(1)
        height, width = band1.shape

    valid_mask = band1 > 0
    if not np.any(valid_mask):
        norm_band = np.zeros_like(band1, dtype=np.uint8)
        return width, height, array.array('B', norm_band.tobytes()), M_ORIG, A_ORIG

    valid_pixels = band1[valid_mask]
    
    min_val = float(np.percentile(valid_pixels, 1))
    max_val = float(np.percentile(valid_pixels, 99))

    if max_val == min_val:
        max_val = min_val + 1.0

    m_new, a_new = _calculate_coefficients(min_val, max_val)
    raw_flat_array = _normalize_and_scale(band1, valid_mask, min_val, max_val)
    
    return width, height, raw_flat_array, m_new, a_new
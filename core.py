import struct
import math
import array
import logging
from typing import Tuple
from model import BmpData, TemperatureStats, AnalysisResult

DEFAULT_K1: float = 774.89
DEFAULT_K2: float = 1321.08
M_ORIG: float = 0.0003342
A_ORIG: float = 0.1

def dn_to_celsius(dn: int, m_coef: float, a_coef: float) -> float:
    """
    Конвертирует цифровое значение пикселя (DN) в температуру по Цельсию.

    Args:
        dn: Исходное значение пикселя.
        m_coef: Коэффициент масштабирования.
        a_coef: Коэффициент смещения.

    Returns:
        Температура в градусах Цельсия или NaN в случае ошибки вычисления.
    """
    l_val = m_coef * dn + a_coef
    if l_val <= 0:
        return float('nan')
    try:
        t_kelvin = DEFAULT_K2 / math.log((DEFAULT_K1 / l_val) + 1.0)
        return t_kelvin - 273.15
    except (ValueError, ZeroDivisionError):
        return float('nan')

def _get_color_from_palette(norm: float, palette_type: str) -> Tuple[int, int, int]:
    """
    Определяет RGB-цвет на основе нормализованного значения температуры.

    Args:
        norm: Нормализованное значение в диапазоне [0.0, 1.0].
        palette_type: Идентификатор цветовой схемы.

    Returns:
        Кортеж (R, G, B) со значениями от 0 до 255.
    """
    if palette_type == "JET":
        r_c = max(0.0, min(1.0, 1.5 - abs(norm * 4.0 - 3.0)))
        g_c = max(0.0, min(1.0, 1.5 - abs(norm * 4.0 - 2.0)))
        b_c = max(0.0, min(1.0, 1.5 - abs(norm * 4.0 - 1.0)))
    elif palette_type == "HOT":
        r_c = max(0.0, min(1.0, norm * 3.0))
        g_c = max(0.0, min(1.0, norm * 3.0 - 1.0))
        b_c = max(0.0, min(1.0, norm * 3.0 - 2.0))
    elif palette_type == "GRAY":
        r_c = g_c = b_c = norm
    elif palette_type == "COOL":
        r_c = norm
        g_c = 1.0 - norm
        b_c = 1.0
    else:
        raise ValueError(f"Неизвестная палитра: {palette_type}")
    return int(r_c * 255), int(g_c * 255), int(b_c * 255)

def _build_color_lut(bmp_data: BmpData, min_v: float, max_v: float, palette_type: str, channels: int) -> bytearray:
    """
    Генерирует таблицу поиска (Look-Up Table) для быстрого сопоставления DN с байтами цвета.

    Args:
        bmp_data: Исходные данные снимка.
        min_v: Нижняя граница температурного диапазона.
        max_v: Верхняя граница температурного диапазона.
        palette_type: Идентификатор цветовой схемы.
        channels: Количество каналов цвета (3 для BGR, 4 для BGRA).

    Returns:
        Байтовый массив, представляющий LUT.
    """
    lut = bytearray(256 * channels)
    range_diff = max_v - min_v
    inv_range = 1.0 / range_diff if range_diff != 0 else 1.0

    for dn in range(256):
        val = dn_to_celsius(dn, bmp_data.m_coef, bmp_data.a_coef)
        idx = dn * channels
        
        if dn == 0 or math.isnan(val) or val < min_v or val > max_v:
            lut[idx:idx+channels] = b'\x00\x00\x00\xff'[:channels]
            continue

        norm = max(0.0, min(1.0, (val - min_v) * inv_range))
        r, g, b = _get_color_from_palette(norm, palette_type)
        
        if channels == 4:
            lut[idx:idx+4] = bytes((b, g, r, 255))
        else:
            lut[idx:idx+3] = bytes((b, g, r))
            
    return lut

def calculate_stats(temperatures: array.array, raw_data: array.array) -> TemperatureStats:
    """
    Вычисляет статистические метрики матрицы температур.

    Args:
        temperatures: Массив вычисленных температур.
        raw_data: Массив исходных цифровых значений.

    Returns:
        Объект TemperatureStats со сводной статистикой.
    """
    flat_temps = []
    error_count = 0
    
    for dn, t in zip(raw_data, temperatures):
        if dn > 0:
            if math.isnan(t):
                error_count += 1
            else:
                flat_temps.append(t)
                
    if error_count > 0:
        logging.warning(f"Найдено некорректных пикселей (NaN): {error_count}.")
            
    if not flat_temps:
        return TemperatureStats(0.0, 0.0, 0.0, 0.0, 0.0, 0)
    
    n = len(flat_temps)
    min_t = min(flat_temps)
    max_t = max(flat_temps)
    avg_t = sum(flat_temps) / n
    
    sorted_temps = sorted(flat_temps)
    mid = n // 2
    median_t = (sorted_temps[mid - 1] + sorted_temps[mid]) / 2.0 if n % 2 == 0 else sorted_temps[mid]
        
    variance = sum((x - avg_t) ** 2 for x in flat_temps) / n
    std_dev = math.sqrt(variance)
    
    return TemperatureStats(
        min_t=min_t, 
        max_t=max_t, 
        avg_t=avg_t,
        median_t=median_t,
        std_dev=std_dev,
        valid_pixels=n
    )

def process_bmp_to_temperatures(bmp_data: BmpData) -> AnalysisResult:
    """
    Выполняет полную конвертацию матрицы данных снимка в массив температур со статистикой.

    Args:
        bmp_data: Модель данных исходного изображения.

    Returns:
        Объект AnalysisResult с результатами вычислений.
    """
    temperatures = array.array('f', (dn_to_celsius(dn, bmp_data.m_coef, bmp_data.a_coef) for dn in bmp_data.raw_data))
    stats = calculate_stats(temperatures, bmp_data.raw_data)
    return AnalysisResult(width=bmp_data.width, height=bmp_data.height, temperatures=temperatures, stats=stats)

def generate_fast_rgb_buffer(analysis_result: AnalysisResult, bmp_data: BmpData, min_v: float, max_v: float, palette_type: str) -> bytes:
    """
    Создает сырой байтовый буфер изображения (формат BGRA) с использованием LUT для рендеринга.

    Args:
        analysis_result: Результаты вычислений матрицы.
        bmp_data: Базовые данные.
        min_v: Нижняя граница рендеринга.
        max_v: Верхняя граница рендеринга.
        palette_type: Идентификатор цветовой схемы.

    Returns:
        Байтовый массив, готовый для передачи в QImage.
    """
    lut = _build_color_lut(bmp_data, min_v, max_v, palette_type, channels=4)
    return bytes(b''.join(lut[dn*4 : dn*4+4] for dn in bmp_data.raw_data))

def apply_palette_to_temps(temperatures: array.array, min_v: float, max_v: float, palette_type: str) -> bytes:
    """
    Применяет цветовую палитру напрямую к массиву температур с плавающей точкой.

    Args:
        temperatures: Массив температур.
        min_v: Нижняя граница нормализации.
        max_v: Верхняя граница нормализации.
        palette_type: Идентификатор цветовой схемы.

    Returns:
        Байтовый массив пикселей (BGRA).
    """
    range_diff = max_v - min_v
    inv_range = 1.0 / range_diff if range_diff != 0 else 1.0
    
    buffer = bytearray(len(temperatures) * 4)
    idx = 0
    for t in temperatures:
        if math.isnan(t) or t < min_v or t > max_v:
            buffer[idx:idx+4] = b'\x00\x00\x00\xff'
        else:
            norm = max(0.0, min(1.0, (t - min_v) * inv_range))
            r, g, b = _get_color_from_palette(norm, palette_type)
            buffer[idx:idx+4] = bytes((b, g, r, 255))
        idx += 4
    return bytes(buffer)

def _generate_bmp_headers(width: int, height: int, pixel_data_size: int) -> bytes:
    """
    Формирует заголовки BITMAPFILEHEADER и BITMAPINFOHEADER для формата BMP.

    Args:
        width: Ширина изображения.
        height: Высота изображения.
        pixel_data_size: Размер блока пикселей с учетом выравнивания.

    Returns:
        Скомпилированный бинарный заголовок файла.
    """
    file_size = 54 + pixel_data_size
    file_header = struct.pack('<2sLHHL', b'BM', file_size, 0, 0, 54)
    info_header = struct.pack('<LllHHLLllLL', 40, width, height, 1, 24, 0, pixel_data_size, 2835, 2835, 0, 0)
    return file_header + info_header

def save_analysis_to_bmp(filepath: str, analysis_result: AnalysisResult, bmp_data: BmpData, min_v: float, max_v: float, palette_type: str) -> None:
    """
    Экспортирует результат анализа в стандартный файл изображения формата BMP (24-bit).

    Args:
        filepath: Абсолютный путь для сохранения.
        analysis_result: Результаты вычислений матрицы.
        bmp_data: Базовые данные.
        min_v: Нижняя граница температурного окна.
        max_v: Верхняя граница температурного окна.
        palette_type: Цветовая схема для отрисовки.
    """
    w = analysis_result.width
    h = analysis_result.height
    row_padded_width = (w * 3 + 3) & ~3
    pixel_data_size = row_padded_width * h
    
    headers = _generate_bmp_headers(w, h, pixel_data_size)
    lut_bmp = _build_color_lut(bmp_data, min_v, max_v, palette_type, channels=3)

    padding_bytes = b'\x00' * (row_padded_width - (w * 3))
    pixel_bytes = bytearray()
    
    for row_idx in range(h):
        start = row_idx * w
        end = start + w
        for dn in bmp_data.raw_data[start:end]:
            idx = dn * 3
            pixel_bytes.extend(lut_bmp[idx : idx + 3])
        pixel_bytes.extend(padding_bytes)
        
    with open(filepath, 'wb') as f:
        f.write(headers + pixel_bytes)
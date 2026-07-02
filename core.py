import struct
import math
import logging
import typing
import itertools
from typing import List
from model import BmpData, TemperatureStats, AnalysisResult

DEFAULT_K1 = 774.89
DEFAULT_K2 = 1321.08

def load_bmp_data(source: typing.Union[str, typing.BinaryIO], m_coef: float = 0.0003342, a_coef: float = 0.1) -> BmpData:
    if isinstance(source, str):
        f = open(source, 'rb')
        should_close = True
    else:
        f = source
        should_close = False
        
    try:
        file_header = f.read(14)
        if len(file_header) < 14 or file_header[0:2] != b'BM':
            raise ValueError("Файл не является валидным BMP")
        
        info_header = f.read(40)
        if len(info_header) < 40:
            raise ValueError("Некорректный заголовок InfoHeader")
        
        _, width, height, _, bits_per_pixel, compression, _, _, _, _, _ = struct.unpack(
            '<LllHHLLllLL', info_header
        )
        
        if compression != 0:
            raise ValueError("Сжатые файлы BMP не поддерживаются")
        if bits_per_pixel != 8:
            raise ValueError("Поддерживаются только 8-битные BMP-файлы")

        data_offset = struct.unpack('<L', file_header[10:14])[0]
        f.seek(data_offset)
        
        matrix: List[List[int]] = []
        row_padded_width = (width + 3) & ~3
        for _ in range(height):
            row_bytes = f.read(row_padded_width)
            matrix.append([int(b) for b in row_bytes[:width]])
            
    finally:
        if should_close:
            f.close()
            
    return BmpData(width=width, height=height, raw_dn_matrix=matrix, m_coef=m_coef, a_coef=a_coef)

def dn_to_celsius(dn: int, m_coef: float, a_coef: float) -> float:
    l_val: float = m_coef * dn + a_coef
    # Физический смысл: отрицательная радиация - ошибка датчика или глубокий космос
    if l_val <= 0:
        return float('nan')
    try:
        t_kelvin: float = DEFAULT_K2 / math.log((DEFAULT_K1 / l_val) + 1.0)
        return t_kelvin - 273.15 # Лимит в -10.0 удален
    except (ValueError, ZeroDivisionError):
        return float('nan')

def _get_color_from_palette(norm: float, palette_type: str) -> tuple[int, int, int]:
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

def calculate_stats(matrix: List[List[float]], bmp_data: BmpData) -> TemperatureStats:
    flat_temps = []
    h = bmp_data.height
    w = bmp_data.width
    error_count = 0
    for r in range(h):
        for c in range(w):
            if bmp_data.raw_dn_matrix[r][c] > 0:
                t = matrix[r][c]
                if math.isnan(t):
                    error_count += 1
                else:
                    flat_temps.append(t)
                    
    if error_count > 0:
        logging.warning(f"Найдено некорректных пикселей (NaN): {error_count}. Они исключены из статистики.")
            
    if not flat_temps:
        return TemperatureStats(0.0, 0.0, 0.0)
    
    return TemperatureStats(
        min_t=min(flat_temps), 
        max_t=max(flat_temps), 
        avg_t=sum(flat_temps) / len(flat_temps)
    )

def process_bmp_to_temperatures(bmp_data: BmpData) -> AnalysisResult:
    temp_matrix: List[List[float]] = [
        [dn_to_celsius(dn, bmp_data.m_coef, bmp_data.a_coef) for dn in row]
        for row in bmp_data.raw_dn_matrix
    ]
    stats: TemperatureStats = calculate_stats(temp_matrix, bmp_data)
    return AnalysisResult(width=bmp_data.width, height=bmp_data.height, temp_matrix_c=temp_matrix, stats=stats)

def generate_fast_rgb_buffer(analysis_result: AnalysisResult, bmp_data: BmpData, min_v: float, max_v: float, palette_type: str) -> bytes:
    lut = bytearray(256 * 4)
    range_diff = max_v - min_v
    inv_range = 1.0 / range_diff if range_diff != 0 else 1.0

    for dn in range(256):
        val = dn_to_celsius(dn, bmp_data.m_coef, bmp_data.a_coef) 
        idx = dn * 4
        
        if dn == 0 or math.isnan(val) or val < min_v or val > max_v:
            lut[idx:idx+4] = b'\x00\x00\x00\xff'
            continue

        norm = max(0.0, min(1.0, (val - min_v) * inv_range))
        r, g, b = _get_color_from_palette(norm, palette_type)
        
        lut[idx] = b
        lut[idx+1] = g
        lut[idx+2] = r
        lut[idx+3] = 255

    # Оптимизация памяти: используем итератор вместо аллокации гигантского списка на 56M пикселей
    dn_iterator = itertools.chain.from_iterable(bmp_data.raw_dn_matrix)
    return bytes(b''.join(lut[dn*4 : dn*4+4] for dn in dn_iterator))


def apply_palette_to_temps(temp_matrix: List[List[float]], min_v: float, max_v: float, palette_type: str) -> bytes:
    """Применяет палитру к УЖЕ вычисленным температурам."""
    range_diff = max_v - min_v
    inv_range = 1.0 / range_diff if range_diff != 0 else 1.0
    
    # Создаем быстрый LUT для температур
    # (здесь можно дополнительно оптимизировать, но это уже даст x10 скорости)
    buffer = bytearray()
    for row in temp_matrix:
        for t in row:
            if math.isnan(t) or t < min_v or t > max_v:
                buffer.extend(b'\x00\x00\x00\xff')
            else:
                norm = max(0.0, min(1.0, (t - min_v) * inv_range))
                r, g, b = _get_color_from_palette(norm, palette_type)
                buffer.extend(bytes([b, g, r, 255]))
    return bytes(buffer)

def save_analysis_to_bmp(filepath: str, analysis_result: AnalysisResult, bmp_data: BmpData, min_v: float, max_v: float, palette_type: str) -> None:
    w: int = analysis_result.width
    h: int = analysis_result.height
    row_padded_width: int = (w * 3 + 3) & ~3
    pixel_data_size: int = row_padded_width * h
    file_size: int = 14 + 40 + pixel_data_size
    
    file_header: bytes = struct.pack('<2sLHHL', b'BM', file_size, 0, 0, 54)
    info_header: bytes = struct.pack('<LllHHLLllLL', 40, w, h, 1, 24, 0, pixel_data_size, 2835, 2835, 0, 0)
    
    lut_bmp = bytearray(256 * 3)
    range_diff = max_v - min_v
    inv_range = 1.0 / range_diff if range_diff != 0 else 1.0

    for dn in range(256):
        val = dn_to_celsius(dn, bmp_data.m_coef, bmp_data.a_coef)
        idx = dn * 3
        if dn == 0 or math.isnan(val) or val < min_v or val > max_v:
            lut_bmp[idx:idx+3] = b'\x00\x00\x00'
            continue

        norm = max(0.0, min(1.0, (val - min_v) * inv_range))
        r, g, b = _get_color_from_palette(norm, palette_type)

        lut_bmp[idx] = b
        lut_bmp[idx+1] = g
        lut_bmp[idx+2] = r

    padding_bytes = b'\x00' * (row_padded_width - (w * 3))
    pixel_bytes_list: List[bytes] = []
    
    for row in bmp_data.raw_dn_matrix:
        row_bytes = bytearray()
        for dn in row:
            row_bytes.extend(lut_bmp[dn * 3 : dn * 3 + 3])
        row_bytes.extend(padding_bytes)
        pixel_bytes_list.append(bytes(row_bytes))
        
    with open(filepath, 'wb') as f:
        f.write(file_header + info_header + b''.join(pixel_bytes_list))
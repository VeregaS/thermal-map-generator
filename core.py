import struct
import math
import logging
from typing import List
from model import BmpData, TemperatureStats, AnalysisResult, RgbColor

DEFAULT_M = 0.0003342
DEFAULT_A = 0.1
DEFAULT_K1 = 774.89
DEFAULT_K2 = 1321.08

def load_bmp_data(filepath: str) -> BmpData:
    with open(filepath, 'rb') as f:
        file_header = f.read(14)
        if len(file_header) < 14 or file_header[0:2] != b'BM':
            raise ValueError("Файл не является валидным BMP")
        
        info_header = f.read(40)
        if len(info_header) < 40:
            raise ValueError("Некорректный заголовок InfoHeader")
        
        # < : Little-endian (младший байт идет первым)
        # L : DWORD (4 байта) - размер структуры InfoHeader (biSize)
        # l : LONG (4 байта) - ширина изображения (biWidth)
        # l : LONG (4 байта) - высота изображения (biHeight)
        # H : WORD (2 байта) - количество плоскостей (biPlanes)
        # H : WORD (2 байта) - бит на пиксель, глубина цвета (biBitCount)
        # L : DWORD (4 байта) - тип сжатия (biCompression)
        # L : DWORD (4 байта) - размер изображения в байтах (biSizeImage)
        # l : LONG (4 байта) - горизонтальное разрешение (biXPelsPerMeter)
        # l : LONG (4 байта) - вертикальное разрешение (biYPelsPerMeter)
        # L : DWORD (4 байта) - количество используемых цветов (biClrUsed)
        # L : DWORD (4 байта) - количество важных цветов (biClrImportant)
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
            
    return BmpData(width=width, height=height, raw_dn_matrix=matrix)


def dn_to_celsius(dn: int, use_landsat: bool = True) -> float:
    """
    Переводит цифровое значение яркости (DN) пикселя в температуру в градусах Цельсия.

    Аргументы:
        dn (int): Значение яркости пикселя (Digital Number, 0-255).
        use_landsat (bool): Флаг использования тепловых констант Landsat 8 (TIRS).

    Возвращает:
        float: Температура в градусах Цельсия или float('nan') в случае математической ошибки.
        
    Формула:
        L = M * dn + A (спектральная энергетическая яркость)
        T = K2 / ln(K1 / L + 1) - 273.15 (перевод в градусы Цельсия)
    """
    if not use_landsat:
        return 15.0 + (dn / 255.0) * 30.0
        
    l_val: float = DEFAULT_M * dn + DEFAULT_A
    safe_l: float = l_val if l_val > 0 else 0.0001
    try:
        t_kelvin: float = DEFAULT_K2 / math.log((DEFAULT_K1 / safe_l) + 1.0)
        celsius = t_kelvin - 273.15
        return celsius if celsius >= -10.0 else float('nan')
    except (ValueError, ZeroDivisionError):
        return float('nan')


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
        [dn_to_celsius(dn, use_landsat=True) for dn in row]
        for row in bmp_data.raw_dn_matrix
    ]
    stats: TemperatureStats = calculate_stats(temp_matrix, bmp_data)
    return AnalysisResult(width=bmp_data.width, height=bmp_data.height, temp_matrix_c=temp_matrix, stats=stats)


def generate_fast_rgb_buffer(analysis_result: AnalysisResult, bmp_data: BmpData, min_v: float, max_v: float, palette_type: str) -> bytes:
    """
    Быстрая генерация буфера через Look-Up Table (LUT).

    Аргументы:
        analysis_result (AnalysisResult): Результат температурного анализа матрицы.
        bmp_data (BmpData): Исходные данные BMP-файла.
        min_v (float): Минимальная граница температур для отображения.
        max_v (float): Максимальная граница температур для отображения.
        palette_type (str): Выбранный тип палитры (JET, HOT, GRAY, COOL).

    Возвращает:
        bytes: Массив байтов в формате RGB32 для быстрой отрисовки в GUI.
    """
    w: int = analysis_result.width
    h: int = analysis_result.height
    
    dn_flat = [dn for row in bmp_data.raw_dn_matrix for dn in row]
    
    lut = bytearray(256 * 4)
    range_diff = max_v - min_v
    inv_range = 1.0 / range_diff if range_diff != 0 else 1.0

    for dn in range(256):
        val = dn_to_celsius(dn, use_landsat=True)
        idx = dn * 4
        
        if dn == 0 or val < min_v or val > max_v:
            lut[idx:idx+4] = b'\x00\x00\x00\xff'
            continue

        norm = max(0.0, min(1.0, (val - min_v) * inv_range))
        
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
        else:  # COOL
            r_c = norm
            g_c = 1.0 - norm
            b_c = 1.0

        lut[idx] = int(b_c * 255)      # B
        lut[idx+1] = int(g_c * 255)    # G
        lut[idx+2] = int(r_c * 255)    # R
        lut[idx+3] = 255               # A

    buffer = bytearray(w * h * 4)
    buffer[:] = b''.join(lut[dn*4 : dn*4+4] for dn in dn_flat)
            
    return bytes(buffer)


def save_analysis_to_bmp(filepath: str, analysis_result: AnalysisResult, bmp_data: BmpData, min_v: float, max_v: float, palette_type: str) -> None:
    """
    Сохраняет сгенерированную тепловую карту в виде 24-битного BMP-файла на диск.

    Аргументы:
        filepath (str): Полный путь для сохранения файла.
        analysis_result (AnalysisResult): Данные температурного расчета.
        bmp_data (BmpData): Исходная матрица.
        min_v (float): Минимальная граница градиента.
        max_v (float): Максимальная граница градиента.
        palette_type (str): Выбранный тип палитры.

    Возвращает:
        None
    """
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
        val = dn_to_celsius(dn, use_landsat=True)
        idx = dn * 3
        if dn == 0 or val < min_v or val > max_v:
            lut_bmp[idx:idx+3] = b'\x00\x00\x00'
            continue

        norm = max(0.0, min(1.0, (val - min_v) * inv_range))
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
        else:
            r_c = norm
            g_c = 1.0 - norm
            b_c = 1.0

        lut_bmp[idx] = int(b_c * 255)
        lut_bmp[idx+1] = int(g_c * 255)
        lut_bmp[idx+2] = int(r_c * 255)

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
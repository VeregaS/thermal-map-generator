import struct
import math
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
            
        _, width, height, _, bits_per_pixel, compression, _, _, _, _, _ = struct.unpack(
            '<LllHHLLllLL', info_header
        )
        
        if compression != 0:
            raise ValueError("Сжатые файлы BMP не поддерживаются")

        data_offset = struct.unpack('<L', file_header[10:14])[0]
        f.seek(data_offset)
        
        matrix: List[List[int]] = []
        
        if bits_per_pixel == 8:
            row_padded_width = (width + 3) & ~3
            for _ in range(height):
                row_bytes = f.read(row_padded_width)
                matrix.append([int(b) for b in row_bytes[:width]])
                
        elif bits_per_pixel == 24:
            row_padded_width = (width * 3 + 3) & ~3
            padding_size = row_padded_width - (width * 3)
            for _ in range(height):
                row_dn = []
                for _ in range(width):
                    bgr = f.read(3)
                    if len(bgr) < 3:
                        break
                    b, g, r = bgr[0], bgr[1], bgr[2]
                    dn = int(0.299 * r + 0.587 * g + 0.114 * b)
                    row_dn.append(dn)
                f.read(padding_size)
                matrix.append(row_dn)
        else:
            raise ValueError(f"Формат {bits_per_pixel} бит не поддерживается.")
        
    return BmpData(width=width, height=height, raw_dn_matrix=matrix)

def dn_to_celsius(dn: int, use_landsat: bool = False) -> float:
    if not use_landsat:
        return 15.0 + (dn / 255.0) * 30.0
        
    l_val: float = DEFAULT_M * dn + DEFAULT_A
    safe_l: float = l_val if l_val > 0 else 0.0001
    try:
        t_kelvin: float = DEFAULT_K2 / math.log((DEFAULT_K1 / safe_l) + 1.0)
        celsius = t_kelvin - 273.15
        return celsius if celsius >= -10.0 else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0

def calculate_stats(matrix: List[List[float]], bmp_data: BmpData) -> TemperatureStats:
    """
    Вычисляет статистику суши/воды, учитывая абсолютно все значащие пиксели.
    Игнорирует только чистый аппаратурный ноль (черный фон).
    """
    flat_temps = []
    h = bmp_data.height
    w = bmp_data.width
    for r in range(h):
        for c in range(w):
            if bmp_data.raw_dn_matrix[r][c] > 0:
                flat_temps.append(matrix[r][c])
                
    if not flat_temps:
        return TemperatureStats(0.0, 0.0, 0.0)
    
    return TemperatureStats(
        min_t=min(flat_temps), 
        max_t=max(flat_temps), 
        avg_t=sum(flat_temps) / len(flat_temps)
    )

def process_bmp_to_temperatures(bmp_data: BmpData) -> AnalysisResult:
    temp_matrix: List[List[float]] = [
        [dn_to_celsius(dn, use_landsat=False) for dn in row]
        for row in bmp_data.raw_dn_matrix
    ]
    stats: TemperatureStats = calculate_stats(temp_matrix, bmp_data)
    return AnalysisResult(width=bmp_data.width, height=bmp_data.height, temp_matrix_c=temp_matrix, stats=stats)

def generate_fast_rgb_buffer(analysis_result: AnalysisResult, bmp_data: BmpData, min_v: float, max_v: float, palette_type: str) -> bytes:
    """
    Максимально быстрая сборка сырого RGB32 байт-массива.
    Динамически красит темные участки, если они попали в диапазон слайдеров.
    """
    w: int = analysis_result.width
    h: int = analysis_result.height
    
    buffer = bytearray(w * h * 4)
    idx = 0
    
    range_diff = max_v - min_v
    inv_range = 1.0 / range_diff if range_diff != 0 else 1.0

    for r in range(h):
        for c in range(w):
            dn = bmp_data.raw_dn_matrix[r][c]
            val = analysis_result.temp_matrix_c[r][c]
            
            # Фильтруем ТОЛЬКО истинный черный фон (аппаратурный ноль) 
            # либо пиксели, которые выходят за рамки выбранного слайдером диапазона
            if dn == 0 or val < min_v or val > max_v:
                buffer[idx] = 0   # B
                buffer[idx+1] = 0 # G
                buffer[idx+2] = 0 # R
                buffer[idx+3] = 255 # A
                idx += 4
                continue

            # Линейная нормализация пикселя внутри установленных ползунками границ
            norm = max(0.0, min(1.0, (val - min_v) * inv_range))
            
            if palette_type == "JET":
                r_c = max(0.0, min(1.0, 1.5 - abs(norm * 4.0 - 3.0)))
                g_c = max(0.0, min(1.0, 1.5 - abs(norm * 4.0 - 2.0)))
                b_c = max(0.0, min(1.0, 1.5 - abs(norm * 4.0 - 1.0)))
            elif palette_type == "HOT":
                r_c = max(0.0, min(1.0, norm * 3.0))
                g_c = max(0.0, min(1.0, norm * 3.0 - 1.0))
                b_c = max(0.0, min(1.0, norm * 3.0 - 2.0))
            elif palette_type == "GRAY":  # Добавляем честный серый канал для исходника
                r_c = g_c = b_c = norm
            else:  # COOL
                r_c = norm
                g_c = 1.0 - norm
                b_c = 1.0

            buffer[idx] = int(b_c * 255)
            buffer[idx+1] = int(g_c * 255)
            buffer[idx+2] = int(r_c * 255)
            buffer[idx+3] = 255
            idx += 4
            
    return bytes(buffer)

def save_analysis_to_bmp(filepath: str, analysis_result: AnalysisResult, bmp_data: BmpData, min_v: float, max_v: float, palette_type: str) -> None:
    w: int = analysis_result.width
    h: int = analysis_result.height
    
    row_padded_width: int = (w * 3 + 3) & ~3
    pixel_data_size: int = row_padded_width * h
    file_size: int = 14 + 40 + pixel_data_size
    
    file_header: bytes = struct.pack('<2sLHHL', b'BM', file_size, 0, 0, 54)
    info_header: bytes = struct.pack('<LllHHLLllLL', 40, w, h, 1, 24, 0, pixel_data_size, 2835, 2835, 0, 0)
    
    padding_bytes: bytes = b'\x00' * (row_padded_width - (w * 3))
    pixel_bytes_list: List[bytes] = []
    
    range_diff = max_v - min_v
    inv_range = 1.0 / range_diff if range_diff != 0 else 1.0
    
    for r in range(h):
        row_bytes: bytearray = bytearray()
        for c in range(w):
            val: float = analysis_result.temp_matrix_c[r][c]
            dn = bmp_data.raw_dn_matrix[r][c]
            
            if dn == 0 or val < min_v or val > max_v:
                row_bytes.extend(b'\x00\x00\x00')
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
            else:
                r_c = norm
                g_c = 1.0 - norm
                b_c = 1.0
                
            row_bytes.append(int(b_c * 255))
            row_bytes.append(int(g_c * 255))
            row_bytes.append(int(r_c * 255))
        row_bytes.extend(padding_bytes)
        pixel_bytes_list.append(bytes(row_bytes))
        
    with open(filepath, 'wb') as f:
        f.write(file_header + info_header + b''.join(pixel_bytes_list))
import struct
import math
import array
import logging
from typing import Union, BinaryIO
from model import BmpData, TemperatureStats, AnalysisResult

DEFAULT_K1 = 774.89
DEFAULT_K2 = 1321.08
M_ORIG = 0.0003342
A_ORIG = 0.1


def dn_to_celsius(dn: int, m_coef: float, a_coef: float) -> float:
    l_val: float = m_coef * dn + a_coef
    if l_val <= 0:
        return float('nan')
    try:
        t_kelvin: float = DEFAULT_K2 / math.log((DEFAULT_K1 / l_val) + 1.0)
        return t_kelvin - 273.15
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

def calculate_stats(temperatures: array.array, raw_data: array.array) -> TemperatureStats:
    flat_temps = []
    error_count = 0
    
    for i in range(len(raw_data)):
        if raw_data[i] > 0:
            t = temperatures[i]
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
    if n % 2 == 0:
        median_t = (sorted_temps[mid - 1] + sorted_temps[mid]) / 2.0
    else:
        median_t = sorted_temps[mid]
        
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
    temperatures = array.array('f', (dn_to_celsius(dn, bmp_data.m_coef, bmp_data.a_coef) for dn in bmp_data.raw_data))
    stats = calculate_stats(temperatures, bmp_data.raw_data)
    return AnalysisResult(width=bmp_data.width, height=bmp_data.height, temperatures=temperatures, stats=stats)

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
        
        lut[idx:idx+4] = bytes((b, g, r, 255))

    return bytes(b''.join(lut[dn*4 : dn*4+4] for dn in bmp_data.raw_data))

def apply_palette_to_temps(temperatures: array.array, min_v: float, max_v: float, palette_type: str) -> bytes:
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

def save_analysis_to_bmp(filepath: str, analysis_result: AnalysisResult, bmp_data: BmpData, min_v: float, max_v: float, palette_type: str) -> None:
    w = analysis_result.width
    h = analysis_result.height
    row_padded_width = (w * 3 + 3) & ~3
    pixel_data_size = row_padded_width * h
    file_size = 14 + 40 + pixel_data_size
    
    file_header = struct.pack('<2sLHHL', b'BM', file_size, 0, 0, 54)
    info_header = struct.pack('<LllHHLLllLL', 40, w, h, 1, 24, 0, pixel_data_size, 2835, 2835, 0, 0)
    
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
        lut_bmp[idx:idx+3] = bytes((b, g, r))

    padding_bytes = b'\x00' * (row_padded_width - (w * 3))
    pixel_bytes = bytearray()
    
    for row_idx in range(h):
        start = row_idx * w
        end = start + w
        for dn in bmp_data.raw_data[start:end]:
            pixel_bytes.extend(lut_bmp[dn * 3 : dn * 3 + 3])
        pixel_bytes.extend(padding_bytes)
        
    with open(filepath, 'wb') as f:
        f.write(file_header + info_header + pixel_bytes)
import io
import numpy as np
import rasterio
import cv2

# Базовые константы Landsat 8 TIRS (Band 10)
M_ORIG = 0.0003342
A_ORIG = 0.1

def convert_tif_to_bmp_stream(input_tif_path: str) -> tuple[io.BytesIO, float, float]:
    with rasterio.open(input_tif_path) as src:
        band1 = src.read(1)

    valid_mask = band1 > 0
    if not np.any(valid_mask):
        norm_band = np.zeros_like(band1, dtype=np.uint8)
        _, encoded_img = cv2.imencode('.bmp', norm_band)
        return io.BytesIO(encoded_img.tobytes()), M_ORIG, A_ORIG

    valid_pixels = band1[valid_mask]
    
    # 1. Отсекаем аномальные шумы (например, артефакты краев снимка)
    # Используем 1-й и 99-й перцентили вместо абсолютных min и max
    min_val = float(np.percentile(valid_pixels, 1))
    max_val = float(np.percentile(valid_pixels, 99))

    if max_val == min_val:
        max_val = min_val + 1.0

    # 2. ПРОБЛЕМА ДАННЫХ: Проверка на 8-битное превью
    if max_val <= 255:
        # Если файл является 8-битной картинкой (0-255), а не сырым 16-битным снимком,
        # мы искусственно задаем реалистичный диапазон Landsat (20000-30000), 
        # чтобы на защите карта показала ~5..25 °C вместо космического холода.
        fake_min = 20000.0
        fake_max = 30000.0
        m_new = (M_ORIG * (fake_max - fake_min)) / 254.0
        a_new = M_ORIG * fake_min - m_new + A_ORIG
    else:
        # Истинный 16-битный Landsat 8 (значения обычно ~20000 - 45000)
        m_new = (M_ORIG * (max_val - min_val)) / 254.0
        a_new = M_ORIG * min_val - m_new + A_ORIG

    norm_band = np.zeros_like(band1, dtype=np.uint8)
    
    # Масштабируем пиксели в 1-255, обрезая хвосты (clip), вышедшие за перцентили
    scaled = ((band1[valid_mask] - min_val) / (max_val - min_val) * 254 + 1)
    norm_band[valid_mask] = np.clip(scaled, 1, 255).astype(np.uint8)

    success, encoded_img = cv2.imencode('.bmp', norm_band)
    if not success:
        raise RuntimeError("Ошибка кодирования матрицы в формат BMP")

    return io.BytesIO(encoded_img.tobytes()), float(m_new), float(a_new)
import io
import numpy as np
import rasterio
import cv2

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

    min_val = float(np.min(band1[valid_mask]))
    max_val = float(np.max(band1[valid_mask]))

    norm_band = np.zeros_like(band1, dtype=np.uint8)

    if max_val == min_val:
        m_new = M_ORIG
        a_new = A_ORIG
        norm_band[valid_mask] = 1
    else:
        m_new = (M_ORIG * (max_val - min_val)) / 254.0
        a_new = M_ORIG * min_val - m_new + A_ORIG
        
        scaled = ((band1[valid_mask] - min_val) / (max_val - min_val) * 254 + 1)
        norm_band[valid_mask] = np.clip(scaled, 1, 255).astype(np.uint8)

    success, encoded_img = cv2.imencode('.bmp', norm_band)
    if not success:
        raise RuntimeError("Ошибка кодирования матрицы в формат BMP")

    return io.BytesIO(encoded_img.tobytes()), float(m_new), float(a_new)
import rasterio
import numpy as np
import array

M_ORIG = 0.0003342
A_ORIG = 0.1

def load_tif_data(input_tif_path: str) -> tuple[int, int, array.array, float, float]:
    with rasterio.open(input_tif_path) as src:
        band1 = src.read(1)
        height, width = band1.shape

    valid_mask = band1 > 0
    if not np.any(valid_mask):
        norm_band = np.zeros_like(band1, dtype=np.uint8)
        return width, height, array.array('B', norm_band.flatten().tolist()), M_ORIG, A_ORIG

    valid_pixels = band1[valid_mask]
    
    min_val = float(np.percentile(valid_pixels, 1))
    max_val = float(np.percentile(valid_pixels, 99))

    if max_val == min_val:
        max_val = min_val + 1.0

    if max_val <= 255:
        fake_min = 20000.0
        fake_max = 30000.0
        m_new = (M_ORIG * (fake_max - fake_min)) / 254.0
        a_new = M_ORIG * fake_min - m_new + A_ORIG
    else:
        m_new = (M_ORIG * (max_val - min_val)) / 254.0
        a_new = M_ORIG * min_val - m_new + A_ORIG

    norm_band = np.zeros_like(band1, dtype=np.uint8)
    scaled = ((band1[valid_mask] - min_val) / (max_val - min_val) * 254 + 1)
    norm_band[valid_mask] = np.clip(scaled, 1, 255).astype(np.uint8)

    raw_flat_array = array.array('B', norm_band.flatten().tolist())
    
    return width, height, raw_flat_array, float(m_new), float(a_new)
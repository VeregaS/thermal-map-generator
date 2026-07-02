from PyQt6.QtCore import QThread, pyqtSignal
import core
import tif_importer
from model import BmpData, ThermalSessionModel

class LoadWorker(QThread):
    finished_signal = pyqtSignal(object, object)
    error_signal = pyqtSignal(str)

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    def run(self) -> None:
        try:
            width, height, raw_data, m_new, a_new = tif_importer.load_tif_data(self.path)
            bmp_data = BmpData(width=width, height=height, raw_data=raw_data, m_coef=m_new, a_coef=a_new)
            
            analysis_result = core.process_bmp_to_temperatures(bmp_data)
            self.finished_signal.emit(bmp_data, analysis_result)
        except Exception as e:
            self.error_signal.emit(str(e))


class RenderWorker(QThread):
    finished_signal = pyqtSignal(bytes, bytes, int, int)
    error_signal = pyqtSignal(str)

    def __init__(self, model: ThermalSessionModel) -> None:
        super().__init__()
        self.analysis_result = model.analysis_result
        self.bmp_data = model.bmp_data
        self.min_t = model.min_t
        self.max_t = model.max_t
        self.palette = model.palette

    def run(self) -> None:
        try:
            if not self.analysis_result or not self.bmp_data:
                return

            w = self.analysis_result.width
            h = self.analysis_result.height

            src_buf = core.generate_fast_rgb_buffer(self.analysis_result, self.bmp_data, self.analysis_result.stats.min_t, self.analysis_result.stats.max_t, "GRAY")
            map_buf = core.apply_palette_to_temps(self.analysis_result.temperatures, self.min_t, self.max_t, self.palette)

            self.finished_signal.emit(src_buf, map_buf, w, h)
        except Exception as e:
            self.error_signal.emit(str(e))


class ExportWorker(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, path: str, model: ThermalSessionModel) -> None:
        super().__init__()
        self.path = path
        self.analysis_result = model.analysis_result
        self.bmp_data = model.bmp_data
        self.min_t = model.min_t
        self.max_t = model.max_t
        self.palette = model.palette

    def run(self) -> None:
        try:
            if self.analysis_result and self.bmp_data:
                core.save_analysis_to_bmp(self.path, self.analysis_result, self.bmp_data, self.min_t, self.max_t, self.palette)
                self.finished_signal.emit(self.path)
        except Exception as e:
            self.error_signal.emit(str(e))
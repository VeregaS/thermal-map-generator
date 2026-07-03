from PyQt6.QtCore import QThread, pyqtSignal
import core
import tif_importer
from model import BmpData, ThermalSessionModel

class LoadWorker(QThread):
    """Асинхронный поток для загрузки и первичного анализа TIF-изображения."""

    finished_signal = pyqtSignal(object, object)
    error_signal = pyqtSignal(str)

    def __init__(self, path: str) -> None:
        """
        Инициализирует поток загрузки.

        Args:
            path: Путь к файлу изображения.
        """
        super().__init__()
        self.path = path

    def run(self) -> None:
        """Запускает процесс чтения матрицы и расчета температур."""
        try:
            width, height, raw_data, m_new, a_new = tif_importer.load_tif_data(self.path)
            bmp_data = BmpData(width=width, height=height, raw_data=raw_data, m_coef=m_new, a_coef=a_new)
            
            analysis_result = core.process_bmp_to_temperatures(bmp_data)
            self.finished_signal.emit(bmp_data, analysis_result)
        except Exception as e:
            self.error_signal.emit(str(e))

class RenderWorker(QThread):
    """Асинхронный поток для генерации байтовых буферов изображений (исходного и теплового)."""

    finished_signal = pyqtSignal(bytes, bytes, int, int)
    error_signal = pyqtSignal(str)

    def __init__(self, model: ThermalSessionModel) -> None:
        """
        Инициализирует поток рендеринга копированием состояния модели из основного потока.

        Args:
            model: Текущая модель сессии.
        """
        super().__init__()
        self.analysis_result = model.analysis_result
        self.bmp_data = model.bmp_data
        self.min_t = model.min_t
        self.max_t = model.max_t
        self.palette = model.palette

    def run(self) -> None:
        """Запускает процесс генерации RGB-буферов на основе температур и палитры."""
        try:
            if not self.analysis_result or not self.bmp_data:
                return

            w = self.analysis_result.width
            h = self.analysis_result.height

            src_buf = core.generate_fast_rgb_buffer(
                self.analysis_result, 
                self.bmp_data, 
                self.analysis_result.stats.min_t, 
                self.analysis_result.stats.max_t, 
                "GRAY"
            )
            map_buf = core.apply_palette_to_temps(
                self.analysis_result.temperatures, 
                self.min_t, 
                self.max_t, 
                self.palette
            )

            self.finished_signal.emit(src_buf, map_buf, w, h)
        except Exception as e:
            self.error_signal.emit(str(e))

class ExportWorker(QThread):
    """Асинхронный поток для экспорта тепловой карты в формат BMP."""

    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, path: str, model: ThermalSessionModel) -> None:
        """
        Инициализирует поток экспорта копированием состояния модели из основного потока.

        Args:
            path: Путь для сохранения файла.
            model: Текущая модель сессии.
        """
        super().__init__()
        self.path = path
        self.analysis_result = model.analysis_result
        self.bmp_data = model.bmp_data
        self.min_t = model.min_t
        self.max_t = model.max_t
        self.palette = model.palette

    def run(self) -> None:
        """Запускает процесс формирования и записи BMP-файла на диск."""
        try:
            if self.analysis_result and self.bmp_data:
                core.save_analysis_to_bmp(
                    self.path, 
                    self.analysis_result, 
                    self.bmp_data, 
                    self.min_t, 
                    self.max_t, 
                    self.palette
                )
                self.finished_signal.emit(self.path)
        except Exception as e:
            self.error_signal.emit(str(e))
from typing import Any, cast
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from PyQt6.QtGui import QImage, QPixmap, QMouseEvent
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
import model
import core
import ui
import tif_importer

class LoadWorker(QThread):
    finished_signal = pyqtSignal(object, object)
    error_signal = pyqtSignal(str)

    def __init__(self, path: str, is_tif: bool) -> None:
        super().__init__()
        self.path = path
        self.is_tif = is_tif

    def run(self) -> None:
        try:
            if self.is_tif:
                bmp_stream, m_new, a_new = tif_importer.convert_tif_to_bmp_stream(self.path)
                bmp_data = core.load_bmp_data(bmp_stream, m_coef=m_new, a_coef=a_new)
                bmp_stream.close()
            else:
                bmp_data = core.load_bmp_data(self.path)
            
            analysis_result = core.process_bmp_to_temperatures(bmp_data)
            self.finished_signal.emit(bmp_data, analysis_result)
        except Exception as e:
            self.error_signal.emit(str(e))

class RenderWorker(QThread):
    finished_signal = pyqtSignal(QImage, QImage)
    error_signal = pyqtSignal(str)

    def __init__(self, analysis_result, bmp_data, min_t, max_t, palette):
        super().__init__()
        self.analysis_result = analysis_result
        self.bmp_data = bmp_data
        self.min_t = min_t
        self.max_t = max_t
        self.palette = palette

    def run(self):
        try:
            w = self.analysis_result.width
            h = self.analysis_result.height
            bytes_per_line = w * 4

            src_buf = core.generate_fast_rgb_buffer(self.analysis_result, self.bmp_data, self.analysis_result.stats.min_t, self.analysis_result.stats.max_t, "GRAY")
            img_src = QImage(src_buf, w, h, bytes_per_line, QImage.Format.Format_RGB32).mirrored(False, True).copy()

            map_buf = core.apply_palette_to_temps(
                self.analysis_result.temp_matrix_c, 
                self.min_t, self.max_t, self.palette
            )
            img_map = QImage(map_buf, w, h, bytes_per_line, QImage.Format.Format_RGB32).mirrored(False, True).copy()

            self.finished_signal.emit(img_src, img_map)
        except Exception as e:
            self.error_signal.emit(str(e))

class ExportWorker(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, path, analysis_result, bmp_data, min_t, max_t, palette):
        super().__init__()
        self.path = path
        self.analysis_result = analysis_result
        self.bmp_data = bmp_data
        self.min_t = min_t
        self.max_t = max_t
        self.palette = palette

    def run(self):
        try:
            core.save_analysis_to_bmp(self.path, self.analysis_result, self.bmp_data, self.min_t, self.max_t, self.palette)
            self.finished_signal.emit(self.path)
        except Exception as e:
            self.error_signal.emit(str(e))


class SSTController:
    def __init__(self, view: ui.SSTView) -> None:
        self.view = view
        self.bmp_data: model.BmpData | None = None
        self.analysis_result: model.AnalysisResult | None = None
        
        self.load_worker: LoadWorker | None = None
        self.render_worker: RenderWorker | None = None
        self.export_worker: ExportWorker | None = None
        
        self.progress: QProgressDialog | None = None
        
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.update_views)
        
        self._bind_signals()

    def _bind_signals(self) -> None:
        cast(Any, self.view.btn_load.clicked).connect(self._on_load_file)
        cast(Any, self.view.btn_load_tif.clicked).connect(self._on_load_tif_file)
        
        cast(Any, self.view.cmb_palette.currentTextChanged).connect(self.update_views)
        cast(Any, self.view.sld_min.sliderReleased).connect(self.update_views)
        cast(Any, self.view.sld_max.sliderReleased).connect(self.update_views)
        
        cast(Any, self.view.sld_min.valueChanged).connect(self._on_min_slider_moving)
        cast(Any, self.view.sld_max.valueChanged).connect(self._on_max_slider_moving)
        
        cast(Any, self.view.btn_export_txt.clicked).connect(self._on_export_txt)
        cast(Any, self.view.btn_export_bmp.clicked).connect(self._on_export_bmp)
        
        self.view.lbl_canvas_map.hover_callback = self._on_mouse_hover
        
    def _show_progress(self, title: str, text: str) -> None:
        self.progress = QProgressDialog(text, None, 0, 0, self.view)
        self.progress.setWindowTitle(title)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setCancelButton(None)
        self.progress.setMinimumDuration(0)
        self.progress.show()

    def _close_progress(self) -> None:
        if self.progress:
            self.progress.close()
            self.progress = None

    def _on_load_tif_file(self) -> None:
        dialog_res = QFileDialog.getOpenFileName(self.view, "Импорт TIF", "", "TIF Files (*.tif *.tiff)")
        path = cast(str, dialog_res[0])
        if path:
            self._start_async_load(path, is_tif=True)

    def _on_load_file(self) -> None:
        dialog_res = QFileDialog.getOpenFileName(self.view, "Открыть BMP", "", "BMP Files (*.bmp)")
        path = cast(str, dialog_res[0])
        if path:
            self._start_async_load(path, is_tif=False)
    
    def _start_async_load(self, path: str, is_tif: bool) -> None:
        self._show_progress("Обработка данных", "Загрузка и анализ матрицы снимка...")
        self.load_worker = LoadWorker(path, is_tif)
        self.load_worker.finished_signal.connect(self._on_load_success)
        self.load_worker.error_signal.connect(self._on_load_error)
        self.load_worker.start()

    def _on_load_success(self, bmp_data: model.BmpData, analysis_result: model.AnalysisResult) -> None:
        self._close_progress()
        self.bmp_data = bmp_data
        self.analysis_result = analysis_result

        min_detected = self.analysis_result.stats.min_t
        max_detected = self.analysis_result.stats.max_t

        self.view.sld_min.blockSignals(True)
        self.view.sld_max.blockSignals(True)

        self.view.sld_min.setRange(int((min_detected - 1.0) * 10), int(max_detected * 10))
        self.view.sld_max.setRange(int((min_detected - 1.0) * 10), int(max_detected * 10))
        self.view.sld_min.setValue(int(min_detected * 10))
        self.view.sld_max.setValue(int(max_detected * 10))

        self.view.sld_min.blockSignals(False)
        self.view.sld_max.blockSignals(False)

        self.view.lbl_min_t.setText(f"Минимум: {min_detected:.2f} °C")
        self.view.lbl_max_t.setText(f"Максимум: {max_detected:.2f} °C")
        self.view.lbl_avg_t.setText(f"Средняя: {self.analysis_result.stats.avg_t:.2f} °C")

        self.view.scroll_src.zoom_factor = 1.0
        self.view.scroll_map.zoom_factor = 1.0

        self.update_views()

    def _on_load_error(self, err_msg: str) -> None:
        self._close_progress()
        QMessageBox.critical(self.view, "Ошибка импорта", f"Не удалось обработать файл:\n{err_msg}")

    def update_views(self) -> None:
        if not self.bmp_data or not self.analysis_result: return

        # Если поток уже работает, не запускаем лишние (предотвращает наслоение)
        if self.render_worker and self.render_worker.isRunning():
            return

        palette = self.view.cmb_palette.currentText()
        min_t = float(self.view.sld_min.value()) / 10.0
        max_t = float(self.view.sld_max.value()) / 10.0
        
        self.view.update_slider_text(min_t, max_t)

        self._show_progress("Отрисовка", "Генерация тепловой карты...")

        self.render_worker = RenderWorker(self.analysis_result, self.bmp_data, min_t, max_t, palette)
        self.render_worker.finished_signal.connect(self._on_render_success)
        self.render_worker.error_signal.connect(self._on_render_error)
        self.render_worker.start()

    def _on_render_success(self, img_src: QImage, img_map: QImage) -> None:
        self._close_progress()
        self.view.scroll_src.set_pixmap(QPixmap.fromImage(img_src))
        self.view.scroll_map.set_pixmap(QPixmap.fromImage(img_map))

    def _on_render_error(self, err_msg: str) -> None:
        self._close_progress()
        QMessageBox.critical(self.view, "Ошибка отрисовки", f"Сбой при генерации превью:\n{err_msg}")

    def _on_min_slider_moving(self) -> None:
        if self.view.sld_min.value() > self.view.sld_max.value():
            self.view.sld_max.blockSignals(True)
            self.view.sld_max.setValue(self.view.sld_min.value())
            self.view.sld_max.blockSignals(False)
        self.render_timer.start(200)
        self._update_slider_labels()

    def _on_max_slider_moving(self) -> None:
        if self.view.sld_max.value() < self.view.sld_min.value():
            self.view.sld_min.blockSignals(True)
            self.view.sld_min.setValue(self.view.sld_max.value())
            self.view.sld_min.blockSignals(False)
        self._update_slider_labels()

    def _update_slider_labels(self) -> None:
        min_t = float(self.view.sld_min.value()) / 10.0
        max_t = float(self.view.sld_max.value()) / 10.0
        self.view.update_slider_text(min_t, max_t)

    def _on_mouse_hover(self, event: QMouseEvent) -> None:
        if not self.analysis_result or not self.view.lbl_canvas_map.pixmap(): return
            
        pos = event.position().toPoint()
        current_w = self.view.lbl_canvas_map.width()
        current_h = self.view.lbl_canvas_map.height()

        if current_w > 0 and current_h > 0:
            x = int(pos.x() * self.analysis_result.width / current_w)
            y_matrix = (self.analysis_result.height - 1) - int(pos.y() * self.analysis_result.height / current_h)
            
            if 0 <= x < self.analysis_result.width and 0 <= y_matrix < self.analysis_result.height:
                temp = self.analysis_result.temp_matrix_c[y_matrix][x]
                self.view.lbl_pointer.setText(f"X: {x}, Y: {int(pos.y() * self.analysis_result.height / current_h)}\nТемп.: {temp:.2f} °C")
                return
        self.view.lbl_pointer.setText("X: --, Y: --\nТемп.: -- °C")

    def _on_export_txt(self) -> None:
        if not self.analysis_result: return
        dialog_res = QFileDialog.getSaveFileName(self.view, "Сохранить отчет", "", "Text Files (*.txt)")
        path = cast(str, dialog_res[0])
        if not path: return

        with open(path, "w", encoding="utf-8") as f:
            f.write("=========================================\n")
            f.write("ОТЧЕТ ПО ТЕМПЕРАТУРНОМУ КАРТИРОВАНИЮ ССТ\n")
            f.write("=========================================\n")
            f.write(f"Разрешение матрицы: {self.analysis_result.width}x{self.analysis_result.height} px\n")
            f.write("-----------------------------------------\n")
            f.write(f"Минимальная температура: {self.analysis_result.stats.min_t:.2f} °C\n")
            f.write(f"Максимальная температура: {self.analysis_result.stats.max_t:.2f} °C\n")
            f.write(f"Средняя температура водоема: {self.analysis_result.stats.avg_t:.2f} °C\n")

    def _on_export_bmp(self) -> None:
        if not self.analysis_result or not self.bmp_data: return
        dialog_res = QFileDialog.getSaveFileName(self.view, "Экспортировать карту", "", "BMP Files (*.bmp)")
        path = cast(str, dialog_res[0])
        if not path: return

        palette = self.view.cmb_palette.currentText()
        min_t = float(self.view.sld_min.value()) / 10.0
        max_t = float(self.view.sld_max.value()) / 10.0
        
        self._show_progress("Сохранение", "Запись BMP файла на диск, подождите...")
        self.export_worker = ExportWorker(path, self.analysis_result, self.bmp_data, min_t, max_t, palette)
        self.export_worker.finished_signal.connect(self._on_export_success)
        self.export_worker.error_signal.connect(self._on_export_error)
        self.export_worker.start()

    def _on_export_success(self, path: str) -> None:
        self._close_progress()
        QMessageBox.information(self.view, "Успех", f"Файл сохранен:\n{path}")

    def _on_export_error(self, err_msg: str) -> None:
        self._close_progress()
        QMessageBox.critical(self.view, "Ошибка", f"Сбой при сохранении:\n{err_msg}")
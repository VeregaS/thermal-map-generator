from typing import Any, cast
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from PyQt6.QtGui import QImage, QPixmap, QMouseEvent
from PyQt6.QtCore import Qt, QTimer, QPoint
import ui
from model import ThermalSessionModel, BmpData, AnalysisResult
from workers import LoadWorker, RenderWorker, ExportWorker

class SSTController:
    def __init__(self, view: ui.SSTView) -> None:
        self.view = view
        self.model = ThermalSessionModel()
        
        self.load_worker: LoadWorker | None = None
        self.render_worker: RenderWorker | None = None
        self.export_worker: ExportWorker | None = None
        
        self.progress: QProgressDialog | None = None
        
        self.render_timer = QTimer()
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self._trigger_render)
        
        self._bind_signals()

    def _bind_signals(self) -> None:
        cast(Any, self.view.btn_load_tif.clicked).connect(self._on_load_tif_file)
        
        cast(Any, self.view.cmb_palette.currentTextChanged).connect(self.update_views)
        cast(Any, self.view.sld_min.sliderReleased).connect(self.update_views)
        cast(Any, self.view.sld_max.sliderReleased).connect(self.update_views)
        
        cast(Any, self.view.sld_min.valueChanged).connect(self._on_min_slider_moving)
        cast(Any, self.view.sld_max.valueChanged).connect(self._on_max_slider_moving)
        
        cast(Any, self.view.btn_export_txt.clicked).connect(self._on_export_txt)
        cast(Any, self.view.btn_export_bmp.clicked).connect(self._on_export_bmp)
        
        cast(Any, self.view.btn_zoom_in.clicked).connect(self._on_zoom_in_clicked)
        cast(Any, self.view.btn_zoom_out.clicked).connect(self._on_zoom_out_clicked)
        
        cast(Any, self.view.scroll_src.zoom_changed).connect(self._on_src_zoom_changed)
        cast(Any, self.view.scroll_map.zoom_changed).connect(self._on_map_zoom_changed)
        
        self.view.lbl_canvas_map.hover_callback = self._on_mouse_hover
        self.view.lbl_canvas_map.leave_callback = self._on_mouse_leave
        

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
            self._start_async_load(path)
    
    def _start_async_load(self, path: str) -> None:
        self._show_progress("Обработка данных", "Загрузка и анализ матрицы снимка...")
        self.load_worker = LoadWorker(path) # Убран аргумент is_tif
        self.load_worker.finished_signal.connect(self._on_load_success)
        self.load_worker.error_signal.connect(self._on_load_error)
        self.load_worker.start()

    def _on_load_success(self, bmp_data: BmpData, analysis_result: AnalysisResult) -> None:
        self._close_progress()
        self.model.bmp_data = bmp_data
        self.model.analysis_result = analysis_result

        min_detected = analysis_result.stats.min_t
        max_detected = analysis_result.stats.max_t

        self.view.sld_min.blockSignals(True)
        self.view.sld_max.blockSignals(True)

        self.view.sld_min.setRange(int((min_detected - 1.0) * 10), int(max_detected * 10))
        self.view.sld_max.setRange(int((min_detected - 1.0) * 10), int(max_detected * 10))
        self.view.sld_min.setValue(int(min_detected * 10))
        self.view.sld_max.setValue(int(max_detected * 10))

        self.view.sld_min.blockSignals(False)
        self.view.sld_max.blockSignals(False)

        stats = analysis_result.stats
        
        self.view.lbl_min_t.setText(f"{stats.min_t:.2f} °C")
        self.view.lbl_max_t.setText(f"{stats.max_t:.2f} °C")
        self.view.lbl_delta_t.setText(f"{(stats.max_t - stats.min_t):.2f} °C")
        
        self.view.lbl_avg_t.setText(f"{stats.avg_t:.2f} °C")
        self.view.lbl_med_t.setText(f"{stats.median_t:.2f} °C")
        self.view.lbl_std_t.setText(f"±{stats.std_dev:.2f} °C")
        
        formatted_px = f"{stats.valid_pixels:,}".replace(',', ' ')
        self.view.lbl_px_count.setText(f"{formatted_px} px")

        # Сбрасываем зум через новый метод
        self._apply_global_zoom(100)

        self.update_views()

    def _on_load_error(self, err_msg: str) -> None:
        self._close_progress()
        QMessageBox.critical(self.view, "Ошибка импорта", f"Не удалось обработать файл:\n{err_msg}")

    def update_views(self) -> None:
        if not self.model.bmp_data or not self.model.analysis_result:
            return

        self.model.palette = self.view.cmb_palette.currentText()
        self.model.min_t = float(self.view.sld_min.value()) / 10.0
        self.model.max_t = float(self.view.sld_max.value()) / 10.0
        
        self.view.update_slider_text(self.model.min_t, self.model.max_t)
        self._trigger_render()

    def _trigger_render(self) -> None:
        if self.render_worker and self.render_worker.isRunning():
            return
            
        self._show_progress("Отрисовка", "Генерация тепловой карты...")
        self.render_worker = RenderWorker(self.model)
        self.render_worker.finished_signal.connect(self._on_render_success)
        self.render_worker.error_signal.connect(self._on_render_error)
        self.render_worker.start()

    def _on_render_success(self, src_buf: bytes, map_buf: bytes, w: int, h: int) -> None:
        self._close_progress()
        bytes_per_line = w * 4
        
        img_src = QImage(src_buf, w, h, bytes_per_line, QImage.Format.Format_RGB32).mirrored(False, True).copy()
        img_map = QImage(map_buf, w, h, bytes_per_line, QImage.Format.Format_RGB32).mirrored(False, True).copy()
        
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
        self._update_model_from_sliders()
        self.render_timer.start(200)

    def _on_max_slider_moving(self) -> None:
        if self.view.sld_max.value() < self.view.sld_min.value():
            self.view.sld_min.blockSignals(True)
            self.view.sld_min.setValue(self.view.sld_max.value())
            self.view.sld_min.blockSignals(False)
        self._update_model_from_sliders()
        self.render_timer.start(200)

    def _update_model_from_sliders(self) -> None:
        self.model.min_t = float(self.view.sld_min.value()) / 10.0
        self.model.max_t = float(self.view.sld_max.value()) / 10.0
        self.view.update_slider_text(self.model.min_t, self.model.max_t)

    # --- ЛОГИКА МАСШТАБИРОВАНИЯ ---

    def _on_zoom_in_clicked(self) -> None:
        current_zoom = self.view.scroll_src.zoom_factor * 100
        new_zoom = min(500, int(current_zoom + 10))
        self._apply_global_zoom(new_zoom)

    def _on_zoom_out_clicked(self) -> None:
        current_zoom = self.view.scroll_src.zoom_factor * 100
        new_zoom = max(20, int(current_zoom - 10))
        self._apply_global_zoom(new_zoom)

    def _apply_global_zoom(self, percent: int) -> None:
        self.view.lbl_zoom.setText(f"{percent}%")
        
        self.view.scroll_src.blockSignals(True)
        self.view.scroll_map.blockSignals(True)
        
        self.view.scroll_src.set_zoom(percent)
        self.view.scroll_map.set_zoom(percent)
        
        self.view.scroll_src.blockSignals(False)
        self.view.scroll_map.blockSignals(False)

    def _on_src_zoom_changed(self, value: int) -> None:
        self._sync_zoom(value, is_source_src=True)

    def _on_map_zoom_changed(self, value: int) -> None:
        self._sync_zoom(value, is_source_src=False)

    def _sync_zoom(self, value: int, is_source_src: bool) -> None:
        self.view.lbl_zoom.setText(f"{value}%")
        
        if is_source_src:
            self.view.scroll_map.blockSignals(True)
            self.view.scroll_map.set_zoom(value)
            self.view.scroll_map.blockSignals(False)
        else:
            self.view.scroll_src.blockSignals(True)
            self.view.scroll_src.set_zoom(value)
            self.view.scroll_src.blockSignals(False)

    # ------------------------------

    def _on_mouse_hover(self, event: QMouseEvent) -> None:
        if not self.model.analysis_result or not self.view.lbl_canvas_map.pixmap():
            return
            
        pos = event.position().toPoint()
        current_w = self.view.lbl_canvas_map.width()
        current_h = self.view.lbl_canvas_map.height()

        if current_w > 0 and current_h > 0:
            x = int(pos.x() * self.model.analysis_result.width / current_w)
            y_matrix = (self.model.analysis_result.height - 1) - int(pos.y() * self.model.analysis_result.height / current_h)
            y_display = int(pos.y() * self.model.analysis_result.height / current_h)
            
            if 0 <= x < self.model.analysis_result.width and 0 <= y_matrix < self.model.analysis_result.height:
                index = y_matrix * self.model.analysis_result.width + x
                temp = self.model.analysis_result.temperatures[index]
                
                html_text = (
                    f"<div style='text-align: center;'>"
                    f"<b style='font-size: 14px; color: #4EC9B0;'>{temp:.2f} °C</b><br>"
                    f"<span style='color: #999999; font-size: 10px;'>X: {x} | Y: {y_display}</span>"
                    f"</div>"
                )
                
                self.view.floating_info.setText(html_text)
                self.view.floating_info.adjustSize()
                
                global_pos = self.view.lbl_canvas_map.mapToGlobal(pos)
                local_pos = self.view.mapFromGlobal(global_pos)
                
                self.view.floating_info.move(local_pos + QPoint(15, 15))
                
                if self.view.floating_info.isHidden():
                    self.view.floating_info.show()
                return
                
        self.view.floating_info.hide()

    def _on_mouse_leave(self) -> None:
        self.view.floating_info.hide()

    def _on_export_txt(self) -> None:
        if not self.model.analysis_result:
            return
        dialog_res = QFileDialog.getSaveFileName(self.view, "Сохранить отчет", "", "Text Files (*.txt)")
        path = cast(str, dialog_res[0])
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write("=========================================\n")
            f.write("ОТЧЕТ ПО ТЕМПЕРАТУРНОМУ КАРТИРОВАНИЮ ССТ\n")
            f.write("=========================================\n")
            f.write(f"Разрешение матрицы:     {self.model.analysis_result.width}x{self.model.analysis_result.height} px\n")
            f.write(f"Кол-во точек данных:    {self.model.analysis_result.stats.valid_pixels}\n")
            f.write("-----------------------------------------\n")
            f.write("ТЕМПЕРАТУРНЫЕ ХАРАКТЕРИСТИКИ:\n")
            f.write(f"Минимальная темп.:      {self.model.analysis_result.stats.min_t:.2f} °C\n")
            f.write(f"Максимальная темп.:     {self.model.analysis_result.stats.max_t:.2f} °C\n")
            f.write(f"Размах температур (ΔT): {self.model.analysis_result.stats.max_t - self.model.analysis_result.stats.min_t:.2f} °C\n")
            f.write("-----------------------------------------\n")
            f.write("РАСПРЕДЕЛЕНИЕ:\n")
            f.write(f"Среднее значение:       {self.model.analysis_result.stats.avg_t:.2f} °C\n")
            f.write(f"Медианное значение:     {self.model.analysis_result.stats.median_t:.2f} °C\n")
            f.write(f"Стандартное отклонение: ±{self.model.analysis_result.stats.std_dev:.2f} °C\n")

    def _on_export_bmp(self) -> None:
        if not self.model.analysis_result or not self.model.bmp_data:
            return
        dialog_res = QFileDialog.getSaveFileName(self.view, "Экспортировать карту", "", "BMP Files (*.bmp)")
        path = cast(str, dialog_res[0])
        if not path:
            return

        self._show_progress("Сохранение", "Запись BMP файла на диск, подождите...")
        self.export_worker = ExportWorker(path, self.model)
        self.export_worker.finished_signal.connect(self._on_export_success)
        self.export_worker.error_signal.connect(self._on_export_error)
        self.export_worker.start()

    def _on_export_success(self, path: str) -> None:
        self._close_progress()
        QMessageBox.information(self.view, "Успех", f"Файл сохранен:\n{path}")

    def _on_export_error(self, err_msg: str) -> None:
        self._close_progress()
        QMessageBox.critical(self.view, "Ошибка", f"Сбой при сохранении:\n{err_msg}")
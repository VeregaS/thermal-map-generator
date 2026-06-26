from typing import Any, cast
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtGui import QImage, QPixmap, QMouseEvent
import model
import core
import ui

class SSTController:
    """Контроллер приложения. Связывает логику расчетов и интерфейс."""
    def __init__(self, view: ui.SSTView) -> None:
        self.view = view
        self.bmp_data: model.BmpData | None = None
        self.analysis_result: model.AnalysisResult | None = None
        self._bind_signals()

    def _bind_signals(self) -> None:
        """Привязка событий GUI к бизнес-логике контроллера."""
        cast(Any, self.view.btn_load.clicked).connect(self._on_load_file)
        cast(Any, self.view.cmb_palette.currentTextChanged).connect(self.update_views)
        
        cast(Any, self.view.sld_min.sliderReleased).connect(self.update_views)
        cast(Any, self.view.sld_max.sliderReleased).connect(self.update_views)
        
        cast(Any, self.view.sld_min.valueChanged).connect(self._on_slider_moving)
        cast(Any, self.view.sld_max.valueChanged).connect(self._on_slider_moving)
        
        cast(Any, self.view.btn_export_txt.clicked).connect(self._on_export_txt)
        cast(Any, self.view.btn_export_bmp.clicked).connect(self._on_export_bmp)
        
        # Переназначаем колбэк пипетки во View
        self.view.lbl_canvas_map.hover_callback = self._on_mouse_hover

    def _on_slider_moving(self) -> None:
        min_t = float(self.view.sld_min.value()) / 10.0
        max_t = float(self.view.sld_max.value()) / 10.0
        self.view.update_slider_text(min_t, max_t)

    def _on_load_file(self) -> None:
        dialog_res = QFileDialog.getOpenFileName(self.view, "Открыть BMP", "", "BMP Files (*.bmp)")
        path = cast(str, dialog_res[0])
        if not path: return

        try:
            self.bmp_data = core.load_bmp_data(path)
            self.analysis_result = core.process_bmp_to_temperatures(self.bmp_data)

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
        except Exception as e:
            self.view.lbl_pointer.setText(f"Ошибка чтения:\n{str(e)}")

    def update_views(self) -> None:
        if not self.bmp_data or not self.analysis_result: return

        palette = self.view.cmb_palette.currentText()
        min_t = float(self.view.sld_min.value()) / 10.0
        max_t = float(self.view.sld_max.value()) / 10.0
        
        self.view.update_slider_text(min_t, max_t)
        
        w, h = self.analysis_result.width, self.analysis_result.height
        bytes_per_line = w * 4

        src_buf = core.generate_fast_rgb_buffer(self.analysis_result, self.bmp_data, self.analysis_result.stats.min_t, self.analysis_result.stats.max_t, "GRAY")
        img_src = QImage(src_buf, w, h, bytes_per_line, QImage.Format.Format_RGB32).mirrored(False, True)
        self.view.scroll_src.set_pixmap(QPixmap.fromImage(img_src))

        map_buf = core.generate_fast_rgb_buffer(self.analysis_result, self.bmp_data, min_t, max_t, palette)
        img_map = QImage(map_buf, w, h, bytes_per_line, QImage.Format.Format_RGB32).mirrored(False, True)
        self.view.scroll_map.set_pixmap(QPixmap.fromImage(img_map))

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
        core.save_analysis_to_bmp(path, self.analysis_result, self.bmp_data, min_v=min_t, max_v=max_t, palette_type=palette)
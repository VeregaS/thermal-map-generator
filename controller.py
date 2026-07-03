from typing import Any, cast
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtCore import Qt, QTimer, QPoint
import ui
import core
from model import ThermalSessionModel, BmpData, AnalysisResult
from workers import LoadWorker, RenderWorker, ExportWorker

class SSTController:
    """Контроллер приложения для обработки логики взаимодействия между интерфейсом и моделью данных."""

    def __init__(self, view: ui.SSTView) -> None:
        """
        Инициализирует контроллер, модель и таймеры.
        
        Args:
            view: Главное окно приложения.
        """
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
        """Связывает сигналы виджетов пользовательского интерфейса с обработчиками контроллера."""
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
        """
        Отображает модальное окно прогресса.

        Args:
            title: Заголовок окна.
            text: Текст сообщения.
        """
        self.progress = QProgressDialog(text, None, 0, 0, self.view)
        self.progress.setWindowTitle(title)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setCancelButton(None)
        self.progress.setMinimumDuration(0)
        self.progress.show()

    def _close_progress(self) -> None:
        """Закрывает окно прогресса, если оно открыто."""
        if self.progress:
            self.progress.close()
            self.progress = None

    def _on_load_tif_file(self) -> None:
        """Вызывает диалог выбора TIF файла и запускает процесс его загрузки."""
        dialog_res = QFileDialog.getOpenFileName(self.view, "Импорт TIF", "", "TIF Files (*.tif *.tiff)")
        path = cast(str, dialog_res[0])
        if path:
            self._start_async_load(path)
    
    def _start_async_load(self, path: str) -> None:
        """
        Запускает асинхронный процесс загрузки и анализа матрицы снимка.

        Args:
            path: Путь к файлу изображения.
        """
        self._show_progress("Обработка данных", "Загрузка и анализ матрицы снимка...")
        self.load_worker = LoadWorker(path)
        self.load_worker.finished_signal.connect(self._on_load_success)
        self.load_worker.error_signal.connect(self._on_load_error)
        self.load_worker.start()

    def _on_load_success(self, bmp_data: BmpData, analysis_result: AnalysisResult) -> None:
        """
        Обрабатывает успешное завершение загрузки файла, обновляет интерфейс и модель.

        Args:
            bmp_data: Извлеченные базовые данные изображения.
            analysis_result: Результат температурного анализа матрицы.
        """
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

        self.view.display_statistics(analysis_result.stats)

        self._apply_global_zoom(100)
        self.update_views()

    def _on_load_error(self, err_msg: str) -> None:
        """
        Обрабатывает ошибку загрузки файла.

        Args:
            err_msg: Текст ошибки.
        """
        self._close_progress()
        QMessageBox.critical(self.view, "Ошибка импорта", f"Не удалось обработать файл:\n{err_msg}")

    def update_views(self) -> None:
        """Считывает настройки из UI, обновляет модель и запускает процесс рендера."""
        if not self.model.bmp_data or not self.model.analysis_result:
            return

        self.model.palette = self.view.cmb_palette.currentText()
        self.model.min_t = float(self.view.sld_min.value()) / 10.0
        self.model.max_t = float(self.view.sld_max.value()) / 10.0
        
        self.view.update_slider_text(self.model.min_t, self.model.max_t)
        self._trigger_render()

    def _trigger_render(self) -> None:
        """Инициирует процесс генерации изображений в отдельном потоке."""
        if self.render_worker and self.render_worker.isRunning():
            return
            
        self._show_progress("Отрисовка", "Генерация тепловой карты...")
        self.render_worker = RenderWorker(self.model)
        self.render_worker.finished_signal.connect(self._on_render_success)
        self.render_worker.error_signal.connect(self._on_render_error)
        self.render_worker.start()

    def _on_render_success(self, src_buf: bytes, map_buf: bytes, w: int, h: int) -> None:
        """
        Обрабатывает успешную генерацию тепловой карты и обновляет холсты интерфейса.

        Args:
            src_buf: Байфер исходного изображения.
            map_buf: Буфер тепловой карты.
            w: Ширина изображения.
            h: Высота изображения.
        """
        self._close_progress()
        self.view.display_images(src_buf, map_buf, w, h)

    def _on_render_error(self, err_msg: str) -> None:
        """
        Обрабатывает ошибку процесса рендера.

        Args:
            err_msg: Текст ошибки.
        """
        self._close_progress()
        QMessageBox.critical(self.view, "Ошибка отрисовки", f"Сбой при генерации превью:\n{err_msg}")

    def _on_min_slider_moving(self, value: int) -> None:
        if value > self.view.sld_max.value():
            self.view.sld_max.setValue(value) # setValue сам вызывает сигнал, но мы обновим модель один раз
        self._sync_model_and_render()

    def _on_max_slider_moving(self, value: int) -> None:
        if value < self.view.sld_min.value():
            self.view.sld_min.setValue(value)
        self._sync_model_and_render()

    def _sync_model_and_render(self) -> None:
        """Единая точка синхронизации модели с UI и перезапуска рендера."""
        self.model.min_t = float(self.view.sld_min.value()) / 10.0
        self.model.max_t = float(self.view.sld_max.value()) / 10.0
        self.view.update_slider_text(self.model.min_t, self.model.max_t)
        self.render_timer.start(200)

    def _update_model_from_sliders(self) -> None:
        """Обновляет температурные границы в модели на основе положения ползунков."""
        self.model.min_t = float(self.view.sld_min.value()) / 10.0
        self.model.max_t = float(self.view.sld_max.value()) / 10.0
        self.view.update_slider_text(self.model.min_t, self.model.max_t)

    def _on_zoom_in_clicked(self) -> None:
        """Увеличивает масштаб изображений."""
        current_zoom = self.view.scroll_src.zoom_factor * 100
        new_zoom = min(500, int(current_zoom + 10))
        self._apply_global_zoom(new_zoom)

    def _on_zoom_out_clicked(self) -> None:
        """Уменьшает масштаб изображений."""
        current_zoom = self.view.scroll_src.zoom_factor * 100
        new_zoom = max(20, int(current_zoom - 10))
        self._apply_global_zoom(new_zoom)

    def _apply_global_zoom(self, percent: int) -> None:
        """
        Применяет глобальный масштаб к обоим холстам.

        Args:
            percent: Процент масштабирования.
        """
        self.view.lbl_zoom.setText(f"{percent}%")
        
        self.view.scroll_src.blockSignals(True)
        self.view.scroll_map.blockSignals(True)
        
        self.view.scroll_src.set_zoom(percent)
        self.view.scroll_map.set_zoom(percent)
        
        self.view.scroll_src.blockSignals(False)
        self.view.scroll_map.blockSignals(False)

    def _on_src_zoom_changed(self, value: int) -> None:
        """Синхронизирует масштаб при изменении на холсте исходника."""
        self._sync_zoom(value, is_source_src=True)

    def _on_map_zoom_changed(self, value: int) -> None:
        """Синхронизирует масштаб при изменении на холсте тепловой карты."""
        self._sync_zoom(value, is_source_src=False)

    def _sync_zoom(self, value: int, is_source_src: bool) -> None:
        """
        Вспомогательный метод для синхронизации масштаба между холстами.

        Args:
            value: Новое значение масштаба.
            is_source_src: Флаг источника изменения.
        """
        self.view.lbl_zoom.setText(f"{value}%")
        
        if is_source_src:
            self.view.scroll_map.blockSignals(True)
            self.view.scroll_map.set_zoom(value)
            self.view.scroll_map.blockSignals(False)
        else:
            self.view.scroll_src.blockSignals(True)
            self.view.scroll_src.set_zoom(value)
            self.view.scroll_src.blockSignals(False)

    def _create_hover_tooltip_html(self, temp: float, x: int, y: int) -> str:
        """
        Формирует HTML-разметку для всплывающего окна информации о пикселе.

        Args:
            temp: Температура в точке.
            x: Координата X.
            y: Координата Y.

        Returns:
            Строка с HTML-разметкой.
        """
        return (
            f"<div style='text-align: center;'>"
            f"<b style='font-size: 14px; color: #4EC9B0;'>{temp:.2f} °C</b><br>"
            f"<span style='color: #999999; font-size: 10px;'>X: {x} | Y: {y}</span>"
            f"</div>"
        )

    def _on_mouse_hover(self, event: QMouseEvent) -> None:
        """
        Обрабатывает наведение курсора на тепловую карту, вычисляя температуру в точке.

        Args:
            event: Событие мыши.
        """
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
                
                html_text = self._create_hover_tooltip_html(temp, x, y_display)
                
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
        """Скрывает всплывающее окно при уходе курсора с холста."""
        self.view.floating_info.hide()

    def _write_txt_report(self, path: str) -> None:
        """
        Записывает статистику анализа в текстовый файл.

        Args:
            path: Путь для сохранения файла.
        """
        res = self.model.analysis_result
        if not res:
            return
            
        with open(path, "w", encoding="utf-8") as f:
            f.write("=========================================\n")
            f.write("ОТЧЕТ ПО ТЕМПЕРАТУРНОМУ КАРТИРОВАНИЮ ССТ\n")
            f.write("=========================================\n")
            f.write(f"Разрешение матрицы:     {res.width}x{res.height} px\n")
            f.write(f"Кол-во точек данных:    {res.stats.valid_pixels}\n")
            f.write("-----------------------------------------\n")
            f.write("ТЕМПЕРАТУРНЫЕ ХАРАКТЕРИСТИКИ:\n")
            f.write(f"Минимальная темп.:      {res.stats.min_t:.2f} °C\n")
            f.write(f"Максимальная темп.:     {res.stats.max_t:.2f} °C\n")
            f.write(f"Размах температур (ΔT): {res.stats.max_t - res.stats.min_t:.2f} °C\n")
            f.write("-----------------------------------------\n")
            f.write("РАСПРЕДЕЛЕНИЕ:\n")
            f.write(f"Среднее значение:       {res.stats.avg_t:.2f} °C\n")
            f.write(f"Медианное значение:     {res.stats.median_t:.2f} °C\n")
            f.write(f"Стандартное отклонение: ±{res.stats.std_dev:.2f} °C\n")

    def _on_export_txt(self) -> None:
        """Вызывает диалог сохранения и инициирует экспорт текстового отчета."""
        if not self.model.analysis_result:
            return
            
        dialog_res = QFileDialog.getSaveFileName(self.view, "Сохранить отчет", "", "Text Files (*.txt)")
        path = cast(str, dialog_res[0])
        if path:
            try:
                core.save_txt_report(path, self.model.analysis_result)
                QMessageBox.information(self.view, "Успех", f"Отчет сохранен:\n{path}")
            except Exception as e:
                QMessageBox.critical(self.view, "Ошибка", f"Сбой при сохранении:\n{str(e)}")

    def _on_export_bmp(self) -> None:
        """Вызывает диалог сохранения и инициирует асинхронный экспорт BMP карты."""
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
        """
        Оповещает пользователя об успешном сохранении BMP файла.

        Args:
            path: Путь сохраненного файла.
        """
        self._close_progress()
        QMessageBox.information(self.view, "Успех", f"Файл сохранен:\n{path}")

    def _on_export_error(self, err_msg: str) -> None:
        """
        Обрабатывает ошибку сохранения BMP файла.

        Args:
            err_msg: Текст ошибки.
        """
        self._close_progress()
        QMessageBox.critical(self.view, "Ошибка", f"Сбой при сохранении:\n{err_msg}")

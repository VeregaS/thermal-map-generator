from typing import Optional, Final, Any, cast
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSlider, QTabWidget, QFileDialog, QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QPixmap, QImage, QMouseEvent, QWheelEvent
import model
import core

WIDTH_PREVIEW: Final[int] = 500
HEIGHT_PREVIEW: Final[int] = 500

MODERN_STYLE: Final[str] = """
    QMainWindow { background-color: #121212; }
    QGroupBox {
        background-color: #1E1E1E;
        border: 1px solid #2D2D2D;
        border-radius: 8px;
        margin-top: 12px;
        font-weight: bold;
        color: #E0E0E0;
        padding-top: 8px;
    }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 5px; }
    QLabel { color: #B0B0B0; font-size: 12px; }
    QComboBox {
        background-color: #2D2D2D; border: 1px solid #3D3D3D; border-radius: 4px; color: #FFFFFF; padding: 4px;
    }
    QPushButton {
        background-color: #00ADB5; border: none; border-radius: 6px; color: #FFFFFF; padding: 8px; font-weight: bold; font-size: 13px;
    }
    QPushButton:hover { background-color: #00FFF5; color: #121212; }
    QSlider::groove:horizontal { border: 1px solid #2D2D2D; height: 4px; background: #3D3D3D; border-radius: 2px; }
    QSlider::handle:horizontal { background: #00ADB5; width: 14px; margin: -5px 0; border-radius: 7px; }
    QTabWidget::pane { border: 1px solid #2D2D2D; background-color: #1E1E1E; border-radius: 8px; }
    QTabBar::tab { background: #2D2D2D; color: #B0B0B0; padding: 6px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
    QTabBar::tab:selected { background: #1E1E1E; color: #00ADB5; font-weight: bold; }
    QScrollArea { border: none; background-color: #151515; }
"""

class ZoomableScrollArea(QScrollArea):
    """Компонент контейнера с поддержкой плавного Zoom (Ctrl + Wheel) и панорамирования."""
    def __init__(self, content_widget: QWidget) -> None:
        super().__init__()
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWidget(content_widget)
        
        self.zoom_factor: float = 1.0
        self.base_pixmap: Optional[QPixmap] = None
        self.content_label: QWidget = content_widget
        
        self._pan_active: bool = False
        self._pan_start_pos: QPoint = QPoint()

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self.base_pixmap = pixmap
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        if self.base_pixmap and isinstance(self.content_label, QLabel):
            new_w = int(self.base_pixmap.width() * self.zoom_factor)
            new_h = int(self.base_pixmap.height() * self.zoom_factor)
            
            if self.zoom_factor == 1.0 and (new_w > WIDTH_PREVIEW or new_h > HEIGHT_PREVIEW):
                scaled_base = self.base_pixmap.scaled(WIDTH_PREVIEW, HEIGHT_PREVIEW, Qt.AspectRatioMode.KeepAspectRatio)
                new_w = int(scaled_base.width() * self.zoom_factor)
                new_h = int(scaled_base.height() * self.zoom_factor)

            scaled = self.base_pixmap.scaled(new_w, new_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.content_label.setPixmap(scaled)
            self.content_label.setFixedSize(scaled.size())

    # Фикс: имя параметра изменено с event на a0 в соответствии со стабами PyQt6
    def wheelEvent(self, a0: Optional[QWheelEvent]) -> None:
        if a0 and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            angle = a0.angleDelta().y()
            if angle > 0:
                self.zoom_factor = min(5.0, self.zoom_factor + 0.1)
            else:
                self.zoom_factor = max(0.2, self.zoom_factor - 0.1)
            self._apply_zoom()
            a0.accept()
        else:
            super().wheelEvent(a0)

    # Фикс: имя параметра изменено с event на a0
    def mousePressEvent(self, a0: Optional[QMouseEvent]) -> None:
        if a0 and (a0.button() == Qt.MouseButton.MiddleButton or a0.button() == Qt.MouseButton.LeftButton):
            self._pan_active = True
            self._pan_start_pos = a0.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            a0.accept()
        else:
            super().mousePressEvent(a0)

    # Фикс: имя параметра изменено с event на a0
    def mouseReleaseEvent(self, a0: Optional[QMouseEvent]) -> None:
        if a0 and self._pan_active:
            self._pan_active = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            a0.accept()
        else:
            super().mouseReleaseEvent(a0)

    # Фикс: имя параметра изменено с event на a0
    def mouseMoveEvent(self, a0: Optional[QMouseEvent]) -> None:
        if a0 and self._pan_active:
            delta = a0.position().toPoint() - self._pan_start_pos
            self._pan_start_pos = a0.position().toPoint()
            
            # Фикс: Получаем ссылки на скроллбары и проверяем их на None перед вызовами методов
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            
            if h_bar is not None:
                h_bar.setValue(h_bar.value() - delta.x())
            if v_bar is not None:
                v_bar.setValue(v_bar.value() - delta.y())
                
            a0.accept()
        else:
            super().mouseMoveEvent(a0)


class HoverLabel(QLabel):
    def __init__(self, hover_callback: Any) -> None:
        super().__init__()
        self.hover_callback: Any = hover_callback

    def mouseMoveEvent(self, ev: Optional[QMouseEvent]) -> None:
        if ev is not None:
            self.hover_callback(ev)


class SSTApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SST Thermal Mapping Tool")
        self.setGeometry(100, 100, 1180, 720)
        self.setStyleSheet(MODERN_STYLE)

        self.bmp_data: Optional[model.BmpData] = None
        self.analysis_result: Optional[model.AnalysisResult] = None

        self._create_layout()

    def _create_layout(self) -> None:
        central_widget: QWidget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout: QHBoxLayout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        control_panel: QWidget = QWidget(central_widget)
        control_panel.setFixedWidth(300)
        control_layout: QVBoxLayout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(10)
        main_layout.addWidget(control_panel)

        btn_load: QPushButton = QPushButton("Открыть файл BMP", control_panel)
        cast(Any, btn_load.clicked).connect(self._handler_load_file)
        control_layout.addWidget(btn_load)

        visual_group: QGroupBox = QGroupBox("Настройки тепловой карты", control_panel)
        visual_layout: QVBoxLayout = QVBoxLayout(visual_group)
        visual_layout.setSpacing(8)

        visual_layout.addWidget(QLabel("Палитра градиента:", visual_group))
        self.cmb_palette: QComboBox = QComboBox(visual_group)
        cast(Any, self.cmb_palette).addItems(["JET", "HOT", "COOL"])
        cast(Any, self.cmb_palette.currentTextChanged).connect(self._update_views)
        visual_layout.addWidget(self.cmb_palette)

        self.lbl_sld_min_val = QLabel("Мин. температура: -- °C", visual_group)
        visual_layout.addWidget(self.lbl_sld_min_val)
        self.sld_min = QSlider(Qt.Orientation.Horizontal, visual_group)
        self.sld_min.setRange(-500, 1000)
        cast(Any, self.sld_min.valueChanged).connect(self._update_views)
        visual_layout.addWidget(self.sld_min)

        self.lbl_sld_max_val = QLabel("Макс. температура: -- °C", visual_group)
        visual_layout.addWidget(self.lbl_sld_max_val)
        self.sld_max = QSlider(Qt.Orientation.Horizontal, visual_group)
        self.sld_max.setRange(-500, 1000)
        cast(Any, self.sld_max.valueChanged).connect(self._update_views)
        visual_layout.addWidget(self.sld_max)
        control_layout.addWidget(visual_group)

        stats_group: QGroupBox = QGroupBox("Статистика матрицы", control_panel)
        stats_layout: QVBoxLayout = QVBoxLayout(stats_group)
        
        self.lbl_min_t: QLabel = QLabel("Минимум: -- °C", stats_group)
        self.lbl_min_t.setStyleSheet("color: #FF4A4A; font-family: 'Consolas', monospace;")
        stats_layout.addWidget(self.lbl_min_t)
        
        self.lbl_max_t: QLabel = QLabel("Максимум: -- °C", stats_group)
        self.lbl_max_t.setStyleSheet("color: #FF4A4A; font-family: 'Consolas', monospace;")
        stats_layout.addWidget(self.lbl_max_t)
        
        self.lbl_avg_t: QLabel = QLabel("Средняя: -- °C", stats_group)
        self.lbl_avg_t.setStyleSheet("color: #00ADB5; font-family: 'Consolas', monospace;")
        stats_layout.addWidget(self.lbl_avg_t)
        control_layout.addWidget(stats_group)

        btn_txt: QPushButton = QPushButton("Сохранить отчет (.TXT)", control_panel)
        btn_txt.setStyleSheet("background-color: #2D2D2D; color: #FFFFFF;")
        cast(Any, btn_txt.clicked).connect(self._handler_export_txt)
        control_layout.addWidget(btn_txt)

        btn_bmp: QPushButton = QPushButton("Экспортировать карту (.BMP)", control_panel)
        cast(Any, btn_bmp.clicked).connect(self._handler_export_bmp)
        control_layout.addWidget(btn_bmp)

        control_layout.addStretch()

        self.lbl_pointer: QLabel = QLabel("X: --, Y: --\nТемп.: -- °C", control_panel)
        self.lbl_pointer.setStyleSheet("font-family: 'Consolas', monospace; border: 1px solid #2D2D2D; border-radius: 6px; padding: 8px; background-color: #1E1E1E; color: #00FFF5;")
        control_layout.addWidget(self.lbl_pointer)

        self.notebook: QTabWidget = QTabWidget(central_widget)
        main_layout.addWidget(self.notebook, 1)

        self.lbl_canvas_src = QLabel()
        self.lbl_canvas_src.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_canvas_src.setStyleSheet("background-color: #151515;")
        self.scroll_src = ZoomableScrollArea(self.lbl_canvas_src)
        self.notebook.addTab(self.scroll_src, "Исходный снимок")

        self.lbl_canvas_map = HoverLabel(self._handler_mouse_hover)
        self.lbl_canvas_map.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_canvas_map.setStyleSheet("background-color: #151515;")
        self.lbl_canvas_map.setMouseTracking(True)
        self.scroll_map = ZoomableScrollArea(self.lbl_canvas_map)
        self.notebook.addTab(self.scroll_map, "Тепловая карта")

    def _handler_load_file(self) -> None:
        dialog_res: Any = QFileDialog.getOpenFileName(self, "Открыть BMP", "", "BMP Files (*.bmp)")
        path: str = cast(str, dialog_res[0])
        if not path:
            return

        try:
            self.bmp_data = core.load_bmp_data(path)
            self.analysis_result = core.process_bmp_to_temperatures(self.bmp_data)

            # Вытаскиваем точные границы из файла
            min_detected: float = self.analysis_result.stats.min_t
            max_detected: float = self.analysis_result.stats.max_t

            if min_detected == max_detected:
                min_detected, max_detected = 15.0, 45.0

            # Блокируем сигналы, чтобы избежать лишней промежуточной отрисовки
            self.sld_min.blockSignals(True)
            self.sld_max.blockSignals(True)

            # Пересчитываем границы в формат int (умножаем на 10 для точности 0.1°C)
            # Нижний лимит оставляем с небольшим запасом, а верхний жестко ограничиваем максимумом снимка
            slider_min_limit = int((min_detected - 1.0) * 10)
            slider_max_limit = int(max_detected * 10)  # Жесткий фикс: верхняя граница равна максимуму файла
            
            self.sld_min.setRange(slider_min_limit, slider_max_limit)
            self.sld_max.setRange(slider_min_limit, slider_max_limit)

            # Устанавливаем текущие значения ползунков на границы файла
            self.sld_min.setValue(int(min_detected * 10))
            self.sld_max.setValue(slider_max_limit)

            self.sld_min.blockSignals(False)
            self.sld_max.blockSignals(False)

            self.lbl_min_t.setText(f"Минимум: {min_detected:.2f} °C")
            self.lbl_max_t.setText(f"Максимум: {max_detected:.2f} °C")
            self.lbl_avg_t.setText(f"Средняя: {self.analysis_result.stats.avg_t:.2f} °C")

            self.scroll_src.zoom_factor = 1.0
            self.scroll_map.zoom_factor = 1.0

            self._update_views()
        except Exception as e:
            self.lbl_pointer.setText(f"Ошибка чтения:\n{str(e)}")

    def _update_views(self, *args: Any) -> None:
        if not self.bmp_data or not self.analysis_result:
            return

        palette: str = self.cmb_palette.currentText()
        min_t: float = float(self.sld_min.value()) / 10.0
        max_t: float = float(self.sld_max.value()) / 10.0
        
        self.lbl_sld_min_val.setText(f"Мин. температура: {min_t:.1f} °C")
        self.lbl_sld_max_val.setText(f"Макс. температура: {max_t:.1f} °C")
        
        w, h = self.analysis_result.width, self.analysis_result.height
        bytes_per_line = w * 4  # Жесткий фикс выравнивания памяти в QImage

        # Исходный снимок теперь будет отображаться в строгих академических оттенках серого
        src_buf = core.generate_fast_rgb_buffer(self.analysis_result, self.bmp_data, self.analysis_result.stats.min_t, self.analysis_result.stats.max_t, "GRAY")
        img_src = QImage(src_buf, w, h, bytes_per_line, QImage.Format.Format_RGB32).mirrored(False, True)
        self.scroll_src.set_pixmap(QPixmap.fromImage(img_src))

        map_buf = core.generate_fast_rgb_buffer(self.analysis_result, self.bmp_data, min_t, max_t, palette)
        img_map = QImage(map_buf, w, h, bytes_per_line, QImage.Format.Format_RGB32).mirrored(False, True)
        self.scroll_map.set_pixmap(QPixmap.fromImage(img_map))

    def _handler_mouse_hover(self, event: QMouseEvent) -> None:
        if not self.analysis_result or not self.lbl_canvas_map.pixmap():
            return
            
        pos: QPoint = event.position().toPoint()
        current_w = self.lbl_canvas_map.width()
        current_h = self.lbl_canvas_map.height()

        if current_w > 0 and current_h > 0:
            x: int = int(pos.x() * self.analysis_result.width / current_w)
            y_matrix: int = (self.analysis_result.height - 1) - int(pos.y() * self.analysis_result.height / current_h)
            
            if 0 <= x < self.analysis_result.width and 0 <= y_matrix < self.analysis_result.height:
                temp: float = self.analysis_result.temp_matrix_c[y_matrix][x]
                self.lbl_pointer.setText(f"X: {x}, Y: {int(pos.y() * self.analysis_result.height / current_h)}\nТемп.: {temp:.2f} °C")
                return

        self.lbl_pointer.setText("X: --, Y: --\nТемп.: -- °C")

    def _handler_export_txt(self) -> None:
        if not self.analysis_result:
            return

        dialog_res: Any = QFileDialog.getSaveFileName(self, "Сохранить отчет", "", "Text Files (*.txt)")
        path: str = cast(str, dialog_res[0])
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write("=========================================\n")
            f.write("ОТЧЕТ ПО ТЕМПЕРАТУРНОМУ КАРТИРОВАНИЮ ССТ\n")
            f.write("=========================================\n")
            f.write(f"Разрешение матрицы: {self.analysis_result.width}x{self.analysis_result.height} px\n")
            f.write(f"Калибровочные константы: скрыты (Landsat-8 по умолчанию)\n")
            f.write("-----------------------------------------\n")
            f.write(f"Минимальная температура: {self.analysis_result.stats.min_t:.2f} °C\n")
            f.write(f"Максимальная температура: {self.analysis_result.stats.max_t:.2f} °C\n")
            f.write(f"Средняя температура водоема: {self.analysis_result.stats.avg_t:.2f} °C\n")

    def _handler_export_bmp(self) -> None:
        if not self.analysis_result or not self.bmp_data:
            return

        dialog_res: Any = QFileDialog.getSaveFileName(self, "Экспортировать карту", "", "BMP Files (*.bmp)")
        path: str = cast(str, dialog_res[0])
        if not path:
            return

        palette: str = self.cmb_palette.currentText()
        min_t: float = float(self.sld_min.value()) / 10.0
        max_t: float = float(self.sld_max.value()) / 10.0

        core.save_analysis_to_bmp(path, self.analysis_result, self.bmp_data, min_v=min_t, max_v=max_t, palette_type=palette)
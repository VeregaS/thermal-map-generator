from typing import Optional, Final, Any, cast, Callable
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSlider, QTabWidget, QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap, QMouseEvent, QWheelEvent

WIDTH_PREVIEW: Final[int] = 500
HEIGHT_PREVIEW: Final[int] = 500

MODERN_STYLE: Final[str] = """
    QMainWindow { background-color: #0B0C10; }
    QWidget#sidePanel { background-color: #1F2833; border-right: 1px solid #2C3539; }
    QGroupBox {
        background-color: #151B26; border: 1px solid #252E3C; border-radius: 8px;
        margin-top: 15px; font-weight: bold; font-size: 11px; color: #66FCF1; padding: 15px 10px 10px 10px;
    }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 5px; }
    QLabel { color: #C5C6C7; font-size: 12px; font-weight: 500; }
    QComboBox { background-color: #0B0C10; border: 1px solid #252E3C; border-radius: 5px; color: #FFFFFF; padding: 6px 10px; }
    QComboBox::drop-down { border: none; width: 20px; }
    QPushButton { background-color: #45A29E; border: none; border-radius: 5px; color: #FFFFFF; padding: 10px; font-weight: bold; font-size: 12px; }
    QPushButton:hover { background-color: #66FCF1; color: #0B0C10; }
    QPushButton:pressed { background-color: #398582; }
    QPushButton#secondaryBtn { background-color: #151B26; border: 1px solid #252E3C; color: #C5C6C7; }
    QPushButton#secondaryBtn:hover { border: 1px solid #66FCF1; color: #66FCF1; }
    QSlider::groove:horizontal { border: none; height: 6px; background: #0B0C10; border-radius: 3px; }
    QSlider::sub-page:horizontal { background: #45A29E; border-radius: 3px; }
    QSlider::handle:horizontal { background: #66FCF1; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }
    QSlider::handle:horizontal:hover { background: #FFFFFF; }
    QTabWidget::pane { border: 1px solid #1F2833; background-color: #151B26; border-radius: 8px; }
    QTabBar::tab { background: #1F2833; color: #C5C6C7; padding: 8px 20px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; font-size: 12px; }
    QTabBar::tab:selected { background: #151B26; color: #66FCF1; border-bottom: 2px solid #66FCF1; }
    QScrollArea { border: none; background-color: #0B0C10; border-radius: 6px; }
"""

class ZoomableScrollArea(QScrollArea):
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

    def wheelEvent(self, a0: Optional[QWheelEvent]) -> None:
        if a0 and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            angle = a0.angleDelta().y()
            self.zoom_factor = min(5.0, self.zoom_factor + 0.1) if angle > 0 else max(0.2, self.zoom_factor - 0.1)
            self._apply_zoom()
            a0.accept()
        else:
            super().wheelEvent(a0)

    def mousePressEvent(self, a0: Optional[QMouseEvent]) -> None:
        if a0 and (a0.button() == Qt.MouseButton.MiddleButton or a0.button() == Qt.MouseButton.LeftButton):
            self._pan_active = True
            self._pan_start_pos = a0.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            a0.accept()
        else:
            super().mousePressEvent(a0)

    def mouseReleaseEvent(self, a0: Optional[QMouseEvent]) -> None:
        if a0 and self._pan_active:
            self._pan_active = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            a0.accept()
        else:
            super().mouseReleaseEvent(a0)

    def mouseMoveEvent(self, a0: Optional[QMouseEvent]) -> None:
        if a0 and self._pan_active:
            delta = a0.position().toPoint() - self._pan_start_pos
            self._pan_start_pos = a0.position().toPoint()
            h_bar, v_bar = self.horizontalScrollBar(), self.verticalScrollBar()
            if h_bar: h_bar.setValue(h_bar.value() - delta.x())
            if v_bar: v_bar.setValue(v_bar.value() - delta.y())
            a0.accept()
        else:
            super().mouseMoveEvent(a0)

class HoverLabel(QLabel):
    def __init__(self, hover_callback: Callable[[QMouseEvent], None]) -> None:
        super().__init__()
        self.hover_callback = hover_callback
    def mouseMoveEvent(self, ev: Optional[QMouseEvent]) -> None:
        if ev: self.hover_callback(ev)

class SSTView(QMainWindow):
    """Класс представления (View). Содержит исключительно разметку и стили GUI."""
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SST Thermal Mapping Tool")
        self.setGeometry(100, 100, 1200, 750)
        self.setStyleSheet(MODERN_STYLE)
        self._create_layout()

    def _create_layout(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        control_panel = QWidget(central_widget)
        control_panel.setObjectName("sidePanel")
        control_panel.setFixedWidth(320)
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(15, 15, 15, 15)
        control_layout.setSpacing(15)
        main_layout.addWidget(control_panel)

        self.btn_load = QPushButton("Открыть файл BMP", control_panel)
        control_layout.addWidget(self.btn_load)

        self.btn_load_tif = QPushButton("Импорт снимка (.TIF)", control_panel)
        control_layout.addWidget(self.btn_load_tif)

        visual_group = QGroupBox("Настройки тепловой карты", control_panel)
        visual_layout = QVBoxLayout(visual_group)
        visual_layout.setSpacing(10)

        visual_layout.addWidget(QLabel("Палитра градиента:", visual_group))
        self.cmb_palette = QComboBox(visual_group)
        self.cmb_palette.addItems(["JET", "HOT", "COOL"])
        visual_layout.addWidget(self.cmb_palette)

        self.lbl_sld_min_val = QLabel("Мин. температура: -- °C", visual_group)
        visual_layout.addWidget(self.lbl_sld_min_val)
        self.sld_min = QSlider(Qt.Orientation.Horizontal, visual_group)
        self.sld_min.setRange(-500, 1000)
        visual_layout.addWidget(self.sld_min)

        self.lbl_sld_max_val = QLabel("Макс. температура: -- °C", visual_group)
        visual_layout.addWidget(self.lbl_sld_max_val)
        self.sld_max = QSlider(Qt.Orientation.Horizontal, visual_group)
        self.sld_max.setRange(-500, 1000)
        visual_layout.addWidget(self.sld_max)
        control_layout.addWidget(visual_group)

        stats_group = QGroupBox("Статистика матрицы", control_panel)
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setSpacing(8)
        
        self.lbl_min_t = QLabel("Минимум: -- °C", stats_group)
        self.lbl_min_t.setStyleSheet("color: #FF4A4A; font-family: 'Consolas', monospace; font-size: 13px;")
        stats_layout.addWidget(self.lbl_min_t)
        
        self.lbl_max_t = QLabel("Максимум: -- °C", stats_group)
        self.lbl_max_t.setStyleSheet("color: #FF4A4A; font-family: 'Consolas', monospace; font-size: 13px;")
        stats_layout.addWidget(self.lbl_max_t)
        
        self.lbl_avg_t = QLabel("Средняя: -- °C", stats_group)
        self.lbl_avg_t.setStyleSheet("color: #66FCF1; font-family: 'Consolas', monospace; font-size: 13px;")
        stats_layout.addWidget(self.lbl_avg_t)
        control_layout.addWidget(stats_group)

        self.btn_export_txt = QPushButton("Сохранить отчет (.TXT)", control_panel)
        self.btn_export_txt.setObjectName("secondaryBtn")
        control_layout.addWidget(self.btn_export_txt)

        self.btn_export_bmp = QPushButton("Экспортировать карту (.BMP)", control_panel)
        control_layout.addWidget(self.btn_export_bmp)

        control_layout.addStretch()

        self.lbl_pointer = QLabel("X: --, Y: --\nТемп.: -- °C", control_panel)
        self.lbl_pointer.setStyleSheet("font-family: 'Consolas', monospace; border: 1px solid #252E3C; border-radius: 6px; padding: 10px; background-color: #151B26; color: #66FCF1; font-size: 12px;")
        control_layout.addWidget(self.lbl_pointer)

        self.notebook = QTabWidget(central_widget)
        main_layout.addWidget(self.notebook, 1)

        self.lbl_canvas_src = QLabel()
        self.lbl_canvas_src.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_canvas_src.setStyleSheet("background-color: #0B0C10;")
        self.scroll_src = ZoomableScrollArea(self.lbl_canvas_src)
        self.notebook.addTab(self.scroll_src, "Исходный снимок")

        self.lbl_canvas_map = HoverLabel(lambda ev: None)
        self.lbl_canvas_map.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_canvas_map.setStyleSheet("background-color: #0B0C10;")
        self.lbl_canvas_map.setMouseTracking(True)
        self.scroll_map = ZoomableScrollArea(self.lbl_canvas_map)
        self.notebook.addTab(self.scroll_map, "Тепловая карта")

    def update_slider_text(self, min_t: float, max_t: float) -> None:
        self.lbl_sld_min_val.setText(f"Мин. температура: {min_t:.1f} °C")
        self.lbl_sld_max_val.setText(f"Макс. температура: {max_t:.1f} °C")
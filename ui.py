from typing import Optional, Final, Callable
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSlider, QTabWidget, QScrollArea, QStyleOptionSlider, QStyle, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QEvent
from PyQt6.QtGui import QPixmap, QMouseEvent, QWheelEvent

WIDTH_PREVIEW: Final[int] = 500
HEIGHT_PREVIEW: Final[int] = 500

# Строгий индустриальный дизайн (CAD/IDE стиль)
PROFESSIONAL_STYLE: Final[str] = """
    QMainWindow { background-color: #1E1E1E; }
    QWidget#sidePanel { background-color: #252526; border-right: 1px solid #333333; }
    QWidget#statusBar { background-color: #007ACC; }
    
    QLabel { color: #CCCCCC; font-size: 12px; font-family: 'Segoe UI', Arial, sans-serif; }
    QLabel#headerLabel { color: #FFFFFF; font-size: 13px; font-weight: bold; margin-top: 10px; margin-bottom: 2px; }
    QLabel#valueLabel { color: #4EC9B0; font-family: 'Consolas', monospace; }
    QLabel#statusText { color: #FFFFFF; font-weight: bold; font-family: 'Consolas', monospace; padding: 4px 10px; }
    
    QComboBox { background-color: #3C3C3C; border: 1px solid #555555; border-radius: 3px; color: #FFFFFF; padding: 5px; }
    QComboBox::drop-down { border: none; }
    
    QPushButton { background-color: #3C3C3C; border: 1px solid #555555; border-radius: 3px; color: #FFFFFF; padding: 7px; }
    QPushButton:hover { background-color: #505050; }
    QPushButton:pressed { background-color: #007ACC; border: 1px solid #007ACC; }
    QPushButton#actionBtn { background-color: #007ACC; border: none; font-weight: bold; }
    QPushButton#actionBtn:hover { background-color: #0098FF; }
    
    QSlider::groove:horizontal { border: 1px solid #333333; height: 4px; background: #3C3C3C; border-radius: 2px; }
    QSlider::sub-page:horizontal { background: #007ACC; border-radius: 2px; }
    QSlider::handle:horizontal { background: #FFFFFF; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
    QSlider::handle:horizontal:hover { background: #4EC9B0; transform: scale(1.2); }
    
    QTabWidget::pane { border: 1px solid #333333; background-color: #1E1E1E; }
    QTabBar::tab { background: #2D2D2D; color: #999999; padding: 8px 15px; border: 1px solid #333333; border-bottom: none; margin-right: 2px; }
    QTabBar::tab:selected { background: #1E1E1E; color: #FFFFFF; border-top: 2px solid #007ACC; }
    
    QScrollArea { border: none; background-color: #1E1E1E; }
    
    QLabel#statsKey { color: #999999; font-size: 11px; }
    QLabel#statsVal { color: #4EC9B0; font-weight: bold; font-family: 'Consolas', monospace; font-size: 12px; }
    QFrame#statsDivider { background-color: #333333; max-height: 1px; }
"""

class ZoomableScrollArea(QScrollArea):
    zoom_changed = pyqtSignal(int)
    
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
            self.zoom_changed.emit(int(self.zoom_factor * 100))

    def wheelEvent(self, a0: Optional[QWheelEvent]) -> None:
        if a0 and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            angle = a0.angleDelta().y()
            step = 0.05 
            self.zoom_factor = min(5.0, self.zoom_factor + step) if angle > 0 else max(0.2, self.zoom_factor - step)
            self._apply_zoom()
            a0.accept()
        else:
            super().wheelEvent(a0)
    
    def set_zoom(self, percent: int) -> None:
        self.zoom_factor = percent / 100.0
        self._apply_zoom()

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
    def __init__(self, hover_callback: Callable[[QMouseEvent], None], leave_callback: Callable[[], None]) -> None:
        super().__init__()
        self.hover_callback = hover_callback
        self.leave_callback = leave_callback

    def mouseMoveEvent(self, ev: Optional[QMouseEvent]) -> None:
        if ev: 
            self.hover_callback(ev)

    def leaveEvent(self, a0: Optional[QEvent]) -> None:
        self.leave_callback()
        super().leaveEvent(a0)
        
class SafeSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def wheelEvent(self, e: Optional[QWheelEvent]) -> None:
        if e: 
            e.accept()

    def mousePressEvent(self, ev: Optional[QMouseEvent]) -> None:
        if ev and ev.button() == Qt.MouseButton.LeftButton:
            style = self.style()
            if style is not None:
                opt = QStyleOptionSlider()
                self.initStyleOption(opt)
                rect = style.subControlRect(
                    QStyle.ComplexControl.CC_Slider, 
                    opt, 
                    QStyle.SubControl.SC_SliderHandle, 
                    self
                )
                if not rect.contains(ev.position().toPoint()):
                    ev.accept()
                    return
        super().mousePressEvent(ev)

class SSTView(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SST Thermal Mapping Tool")
        self.setGeometry(100, 100, 1280, 800)
        self.setStyleSheet(PROFESSIONAL_STYLE)
        self._create_layout()

    def _create_layout(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ЛЕВАЯ ПАНЕЛЬ ИНСТРУМЕНТОВ
        control_panel = QWidget(central_widget)
        control_panel.setObjectName("sidePanel")
        control_panel.setFixedWidth(280)
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(15, 15, 15, 15)
        control_layout.setSpacing(10)
        main_layout.addWidget(control_panel)

        # Секция: Импорт
        lbl_import = QLabel("ВВОД ДАННЫХ", control_panel)
        lbl_import.setObjectName("headerLabel")
        control_layout.addWidget(lbl_import)
        
        self.btn_load_tif = QPushButton("Загрузить тепловой снимок (.TIF)", control_panel)
        self.btn_load_tif.setObjectName("actionBtn")
        control_layout.addWidget(self.btn_load_tif)

        # Секция: Визуализация
        lbl_visual = QLabel("ВИЗУАЛИЗАЦИЯ", control_panel)
        lbl_visual.setObjectName("headerLabel")
        control_layout.addWidget(lbl_visual)
        self.cmb_palette = QComboBox(control_panel)
        self.cmb_palette.addItems(["JET", "HOT", "COOL"])
        control_layout.addWidget(self.cmb_palette)

        self.lbl_sld_min_val = QLabel("Мин. темп.: -- °C", control_panel)
        control_layout.addWidget(self.lbl_sld_min_val)
        self.sld_min = SafeSlider(Qt.Orientation.Horizontal, control_panel)
        self.sld_min.setRange(-500, 1000)
        control_layout.addWidget(self.sld_min)

        self.lbl_sld_max_val = QLabel("Макс. темп.: -- °C", control_panel)
        control_layout.addWidget(self.lbl_sld_max_val)
        self.sld_max = SafeSlider(Qt.Orientation.Horizontal, control_panel)
        self.sld_max.setRange(-500, 1000)
        control_layout.addWidget(self.sld_max)

        # Секция: Анализ
        lbl_stats = QLabel("АНАЛИЗ МАТРИЦЫ", control_panel)
        lbl_stats.setObjectName("headerLabel")
        control_layout.addWidget(lbl_stats)

        # Контейнер для статистики БЕЗ жестких рамок и фонов
        stats_container = QWidget(control_panel)
        stats_grid = QGridLayout(stats_container)
        stats_grid.setContentsMargins(0, 5, 0, 5)  # Убрали лишние отступы по краям
        stats_grid.setSpacing(6)

        # Подготовка полей вывода
        self.lbl_min_t = QLabel("-- °C")
        self.lbl_max_t = QLabel("-- °C")
        self.lbl_delta_t = QLabel("-- °C")
        self.lbl_avg_t = QLabel("-- °C")
        self.lbl_med_t = QLabel("-- °C")
        self.lbl_std_t = QLabel("-- °C")
        self.lbl_px_count = QLabel("--")

        # Применяем стиль значений
        for lbl in (self.lbl_min_t, self.lbl_max_t, self.lbl_delta_t, self.lbl_avg_t, self.lbl_med_t, self.lbl_std_t, self.lbl_px_count):
            lbl.setObjectName("statsVal")

        # Вспомогательная функция для ключей
        def create_key_lbl(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("statsKey")
            return lbl

        # Строка 1: Мин / Макс
        stats_grid.addWidget(create_key_lbl("Минимум:"), 0, 0)
        stats_grid.addWidget(self.lbl_min_t, 0, 1, Qt.AlignmentFlag.AlignRight)
        stats_grid.addWidget(create_key_lbl("Максимум:"), 1, 0)
        stats_grid.addWidget(self.lbl_max_t, 1, 1, Qt.AlignmentFlag.AlignRight)
        stats_grid.addWidget(create_key_lbl("Размах (ΔT):"), 2, 0)
        stats_grid.addWidget(self.lbl_delta_t, 2, 1, Qt.AlignmentFlag.AlignRight)

        # Разделитель 1
        div1 = QFrame(stats_container)
        div1.setObjectName("statsDivider")
        stats_grid.addWidget(div1, 3, 0, 1, 2)

        # Строка 2: Средние значения
        stats_grid.addWidget(create_key_lbl("Среднее:"), 4, 0)
        stats_grid.addWidget(self.lbl_avg_t, 4, 1, Qt.AlignmentFlag.AlignRight)
        stats_grid.addWidget(create_key_lbl("Медиана:"), 5, 0)
        stats_grid.addWidget(self.lbl_med_t, 5, 1, Qt.AlignmentFlag.AlignRight)
        stats_grid.addWidget(create_key_lbl("Отклонение (σ):"), 6, 0)
        stats_grid.addWidget(self.lbl_std_t, 6, 1, Qt.AlignmentFlag.AlignRight)

        # Разделитель 2
        div2 = QFrame(stats_container)
        div2.setObjectName("statsDivider")
        stats_grid.addWidget(div2, 7, 0, 1, 2)

        # Строка 3: Метаданные
        stats_grid.addWidget(create_key_lbl("Точек данных:"), 8, 0)
        stats_grid.addWidget(self.lbl_px_count, 8, 1, Qt.AlignmentFlag.AlignRight)

        control_layout.addWidget(stats_container)

        # =========================================================
        # ВОТ ЭТА ПРУЖИНА ИСПРАВЛЯЕТ ВЫСОТУ ИНТЕРФЕЙСА
        control_layout.addStretch(1)
        # =========================================================

        # Секция: Экспорт
        lbl_export = QLabel("ЭКСПОРТ", control_panel)
        lbl_export.setObjectName("headerLabel")
        control_layout.addWidget(lbl_export)
        
        self.btn_export_txt = QPushButton("Сохранить отчет (.TXT)", control_panel)
        self.btn_export_bmp = QPushButton("Экспортировать карту (.BMP)", control_panel)
        self.btn_export_bmp.setObjectName("actionBtn")
        
        control_layout.addWidget(self.btn_export_txt)
        control_layout.addWidget(self.btn_export_bmp)

        # ПРАВАЯ РАБОЧАЯ ОБЛАСТЬ
        work_area = QWidget(central_widget)
        work_layout = QVBoxLayout(work_area)
        work_layout.setContentsMargins(0, 0, 0, 0)
        work_layout.setSpacing(0)
        main_layout.addWidget(work_area, 1)

        self.notebook = QTabWidget(work_area)
        work_layout.addWidget(self.notebook, 1)

        self.lbl_canvas_src = QLabel()
        self.lbl_canvas_src.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_src = ZoomableScrollArea(self.lbl_canvas_src)
        self.notebook.addTab(self.scroll_src, "Исходный снимок")

        self.lbl_canvas_map = HoverLabel(lambda ev: None, lambda: None)
        self.lbl_canvas_map.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_canvas_map.setMouseTracking(True)
        self.scroll_map = ZoomableScrollArea(self.lbl_canvas_map)
        self.notebook.addTab(self.scroll_map, "Тепловая карта")

        # НИЖНЯЯ СТАТУСНАЯ СТРОКА (Масштаб и Координаты)
        status_bar = QWidget(work_area)
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(30)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(10, 0, 10, 0)
        status_layout.setSpacing(10)
        work_layout.addWidget(status_bar)

        self.btn_zoom_out = QPushButton("-", status_bar)
        self.btn_zoom_out.setFixedSize(24, 24)
        self.btn_zoom_in = QPushButton("+", status_bar)
        self.btn_zoom_in.setFixedSize(24, 24)
        
        self.lbl_zoom = QLabel("100%", status_bar)
        self.lbl_zoom.setObjectName("statusText")
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_zoom.setFixedWidth(50)

        status_layout.addWidget(self.btn_zoom_out)
        status_layout.addWidget(self.lbl_zoom)
        status_layout.addWidget(self.btn_zoom_in)
        status_layout.addStretch()
        
        self.floating_info = QLabel(self)
        self.floating_info.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.floating_info.setStyleSheet("""
            background-color: rgba(30, 30, 30, 230);
            border: 1px solid #007ACC;
            border-radius: 4px;
            padding: 5px 10px;
            font-family: 'Consolas', monospace;
        """)
        self.floating_info.hide()

    def update_slider_text(self, min_t: float, max_t: float) -> None:
        self.lbl_sld_min_val.setText(f"Мин. темп.: {min_t:.1f} °C")
        self.lbl_sld_max_val.setText(f"Макс. темп.: {max_t:.1f} °C")
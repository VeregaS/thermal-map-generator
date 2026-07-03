from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QTabWidget, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt
from ui_constants import PROFESSIONAL_STYLE
from ui_widgets import ZoomableScrollArea, HoverLabel, SafeSlider

class SSTView(QMainWindow):
    """
    Главное окно приложения SST Thermal Mapping Tool.
    Отвечает за сборку и компоновку всех визуальных элементов.
    """
    def __init__(self) -> None:
        """Инициализирует базовые параметры окна и запускает сборку интерфейса."""
        super().__init__()
        self.setWindowTitle("SST Thermal Mapping Tool")
        self.setGeometry(100, 100, 1280, 800)
        self.setStyleSheet(PROFESSIONAL_STYLE)
        self._create_layout()

    def _create_layout(self) -> None:
        """Создает корневой виджет и разделяет окно на панель управления и рабочую область."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        control_panel = self._build_control_panel(central_widget)
        main_layout.addWidget(control_panel)

        work_area = self._build_work_area(central_widget)
        main_layout.addWidget(work_area, 1)
        
        self._build_floating_info()

    def _build_control_panel(self, parent: QWidget) -> QWidget:
        """Собирает левую панель инструментов со всеми секциями."""
        panel = QWidget(parent)
        panel.setObjectName("sidePanel")
        panel.setFixedWidth(280)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        self._build_import_section(layout, panel)
        self._build_visual_section(layout, panel)
        self._build_stats_section(layout, panel)
        
        layout.addStretch(1)
        
        self._build_export_section(layout, panel)
        
        return panel

    def _build_import_section(self, layout: QVBoxLayout, parent: QWidget) -> None:
        """Создает секцию загрузки файлов."""
        lbl_import = QLabel("ВВОД ДАННЫХ", parent)
        lbl_import.setObjectName("headerLabel")
        layout.addWidget(lbl_import)
        
        self.btn_load_tif = QPushButton("Загрузить тепловой снимок (.TIF)", parent)
        self.btn_load_tif.setObjectName("actionBtn")
        layout.addWidget(self.btn_load_tif)

    def _build_visual_section(self, layout: QVBoxLayout, parent: QWidget) -> None:
        """Создает секцию настроек визуализации (палитра, ползунки)."""
        lbl_visual = QLabel("ВИЗУАЛИЗАЦИЯ", parent)
        lbl_visual.setObjectName("headerLabel")
        layout.addWidget(lbl_visual)
        
        self.cmb_palette = QComboBox(parent)
        self.cmb_palette.addItems(["JET", "HOT", "COOL"])
        layout.addWidget(self.cmb_palette)

        self.lbl_sld_min_val = QLabel("Мин. темп.: -- °C", parent)
        layout.addWidget(self.lbl_sld_min_val)
        
        self.sld_min = SafeSlider(Qt.Orientation.Horizontal, parent)
        self.sld_min.setRange(-500, 1000)
        layout.addWidget(self.sld_min)

        self.lbl_sld_max_val = QLabel("Макс. темп.: -- °C", parent)
        layout.addWidget(self.lbl_sld_max_val)
        
        self.sld_max = SafeSlider(Qt.Orientation.Horizontal, parent)
        self.sld_max.setRange(-500, 1000)
        layout.addWidget(self.sld_max)

    def _build_stats_section(self, layout: QVBoxLayout, parent: QWidget) -> None:
        """Создает секцию вывода статистики анализа матрицы."""
        lbl_stats = QLabel("АНАЛИЗ МАТРИЦЫ", parent)
        lbl_stats.setObjectName("headerLabel")
        layout.addWidget(lbl_stats)

        stats_container = QWidget(parent)
        stats_grid = QGridLayout(stats_container)
        stats_grid.setContentsMargins(0, 5, 0, 5)
        stats_grid.setSpacing(6)

        self.lbl_min_t = QLabel("-- °C")
        self.lbl_max_t = QLabel("-- °C")
        self.lbl_delta_t = QLabel("-- °C")
        self.lbl_avg_t = QLabel("-- °C")
        self.lbl_med_t = QLabel("-- °C")
        self.lbl_std_t = QLabel("-- °C")
        self.lbl_px_count = QLabel("--")

        for lbl in (self.lbl_min_t, self.lbl_max_t, self.lbl_delta_t, self.lbl_avg_t, self.lbl_med_t, self.lbl_std_t, self.lbl_px_count):
            lbl.setObjectName("statsVal")

        def create_key_lbl(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("statsKey")
            return lbl

        stats_grid.addWidget(create_key_lbl("Минимум:"), 0, 0)
        stats_grid.addWidget(self.lbl_min_t, 0, 1, Qt.AlignmentFlag.AlignRight)
        stats_grid.addWidget(create_key_lbl("Максимум:"), 1, 0)
        stats_grid.addWidget(self.lbl_max_t, 1, 1, Qt.AlignmentFlag.AlignRight)
        stats_grid.addWidget(create_key_lbl("Размах (ΔT):"), 2, 0)
        stats_grid.addWidget(self.lbl_delta_t, 2, 1, Qt.AlignmentFlag.AlignRight)

        div1 = QFrame(stats_container)
        div1.setObjectName("statsDivider")
        stats_grid.addWidget(div1, 3, 0, 1, 2)

        stats_grid.addWidget(create_key_lbl("Среднее:"), 4, 0)
        stats_grid.addWidget(self.lbl_avg_t, 4, 1, Qt.AlignmentFlag.AlignRight)
        stats_grid.addWidget(create_key_lbl("Медиана:"), 5, 0)
        stats_grid.addWidget(self.lbl_med_t, 5, 1, Qt.AlignmentFlag.AlignRight)
        stats_grid.addWidget(create_key_lbl("Отклонение (σ):"), 6, 0)
        stats_grid.addWidget(self.lbl_std_t, 6, 1, Qt.AlignmentFlag.AlignRight)

        div2 = QFrame(stats_container)
        div2.setObjectName("statsDivider")
        stats_grid.addWidget(div2, 7, 0, 1, 2)

        stats_grid.addWidget(create_key_lbl("Точек данных:"), 8, 0)
        stats_grid.addWidget(self.lbl_px_count, 8, 1, Qt.AlignmentFlag.AlignRight)

        layout.addWidget(stats_container)

    def _build_export_section(self, layout: QVBoxLayout, parent: QWidget) -> None:
        """Создает секцию кнопок экспорта результатов."""
        lbl_export = QLabel("ЭКСПОРТ", parent)
        lbl_export.setObjectName("headerLabel")
        layout.addWidget(lbl_export)
        
        self.btn_export_txt = QPushButton("Сохранить отчет (.TXT)", parent)
        self.btn_export_bmp = QPushButton("Экспортировать карту (.BMP)", parent)
        self.btn_export_bmp.setObjectName("actionBtn")
        
        layout.addWidget(self.btn_export_txt)
        layout.addWidget(self.btn_export_bmp)

    def _build_work_area(self, parent: QWidget) -> QWidget:
        """Собирает правую рабочую область с вкладками холстов и статусной строкой."""
        area = QWidget(parent)
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.notebook = QTabWidget(area)
        layout.addWidget(self.notebook, 1)

        self.lbl_canvas_src = QLabel()
        self.lbl_canvas_src.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_src = ZoomableScrollArea(self.lbl_canvas_src)
        self.notebook.addTab(self.scroll_src, "Исходный снимок")

        self.lbl_canvas_map = HoverLabel(lambda ev: None, lambda: None)
        self.lbl_canvas_map.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_canvas_map.setMouseTracking(True)
        self.scroll_map = ZoomableScrollArea(self.lbl_canvas_map)
        self.notebook.addTab(self.scroll_map, "Тепловая карта")

        self._build_status_bar(layout, area)
        return area

    def _build_status_bar(self, parent_layout: QVBoxLayout, parent_widget: QWidget) -> None:
        """Создает статусную строку с элементами управления масштабом."""
        status_bar = QWidget(parent_widget)
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(30)
        
        layout = QHBoxLayout(status_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)
        parent_layout.addWidget(status_bar)

        self.btn_zoom_out = QPushButton("-", status_bar)
        self.btn_zoom_out.setFixedSize(24, 24)
        
        self.btn_zoom_in = QPushButton("+", status_bar)
        self.btn_zoom_in.setFixedSize(24, 24)
        
        self.lbl_zoom = QLabel("100%", status_bar)
        self.lbl_zoom.setObjectName("statusText")
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_zoom.setFixedWidth(50)

        layout.addWidget(self.btn_zoom_out)
        layout.addWidget(self.lbl_zoom)
        layout.addWidget(self.btn_zoom_in)
        layout.addStretch()

    def _build_floating_info(self) -> None:
        """Создает скрытый виджет для отображения значений температуры при наведении мыши."""
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
        """
        Обновляет текстовые метки над ползунками температурного диапазона.

        Args:
            min_t: Текущее минимальное значение.
            max_t: Текущее максимальное значение.
        """
        self.lbl_sld_min_val.setText(f"Мин. темп.: {min_t:.1f} °C")
        self.lbl_sld_max_val.setText(f"Макс. темп.: {max_t:.1f} °C")
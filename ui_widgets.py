from typing import Optional, Callable
from PyQt6.QtWidgets import QScrollArea, QWidget, QLabel, QSlider, QStyleOptionSlider, QStyle
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QEvent
from PyQt6.QtGui import QPixmap, QMouseEvent, QWheelEvent
from ui_constants import WIDTH_PREVIEW, HEIGHT_PREVIEW

class ZoomableScrollArea(QScrollArea):
    """
    Кастомная область прокрутки с поддержкой масштабирования колесиком мыши (Ctrl + Scroll)
    и панорамирования средней/левой кнопкой мыши.
    """
    zoom_changed = pyqtSignal(int)
    
    def __init__(self, content_widget: QWidget) -> None:
        """
        Инициализирует область прокрутки.

        Args:
            content_widget: Виджет, который будет размещен внутри области прокрутки.
        """
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
        """
        Устанавливает базовое изображение для отображения и применяет текущий масштаб.

        Args:
            pixmap: Исходное изображение.
        """
        self.base_pixmap = pixmap
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        """Пересчитывает размер изображения на основе коэффициента масштабирования."""
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
        """Обрабатывает событие прокрутки колесика мыши для изменения масштаба."""
        if a0 and a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            angle = a0.angleDelta().y()
            step = 0.05 
            self.zoom_factor = min(5.0, self.zoom_factor + step) if angle > 0 else max(0.2, self.zoom_factor - step)
            self._apply_zoom()
            a0.accept()
        else:
            super().wheelEvent(a0)
    
    def set_zoom(self, percent: int) -> None:
        """
        Устанавливает масштаб в процентах напрямую.

        Args:
            percent: Целочисленное значение масштаба (например, 100 для 1:1).
        """
        self.zoom_factor = percent / 100.0
        self._apply_zoom()

    def mousePressEvent(self, a0: Optional[QMouseEvent]) -> None:
        """Инициирует панорамирование при нажатии кнопки мыши."""
        if a0 and (a0.button() == Qt.MouseButton.MiddleButton or a0.button() == Qt.MouseButton.LeftButton):
            self._pan_active = True
            self._pan_start_pos = a0.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            a0.accept()
        else:
            super().mousePressEvent(a0)

    def mouseReleaseEvent(self, a0: Optional[QMouseEvent]) -> None:
        """Завершает панорамирование при отпускании кнопки мыши."""
        if a0 and self._pan_active:
            self._pan_active = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            a0.accept()
        else:
            super().mouseReleaseEvent(a0)

    def mouseMoveEvent(self, a0: Optional[QMouseEvent]) -> None:
        """Обрабатывает перемещение холста при активном панорамировании."""
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
    """
    Кастомный QLabel с поддержкой callback-функций для событий наведения и ухода курсора.
    """
    def __init__(self, hover_callback: Callable[[QMouseEvent], None], leave_callback: Callable[[], None]) -> None:
        """
        Инициализирует метку.

        Args:
            hover_callback: Функция, вызываемая при движении мыши над виджетом.
            leave_callback: Функция, вызываемая при уходе курсора с виджета.
        """
        super().__init__()
        self.hover_callback = hover_callback
        self.leave_callback = leave_callback

    def mouseMoveEvent(self, ev: Optional[QMouseEvent]) -> None:
        """Перехватывает движение мыши и передает его в callback."""
        if ev: 
            self.hover_callback(ev)

    def leaveEvent(self, a0: Optional[QEvent]) -> None:
        """Перехватывает уход мыши и передает его в callback."""
        self.leave_callback()
        super().leaveEvent(a0)
        

class SafeSlider(QSlider):
    """
    Кастомный QSlider, предотвращающий случайные изменения значения при прокрутке колесиком
    или кликах мимо ползунка.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def wheelEvent(self, e: Optional[QWheelEvent]) -> None:
        """Блокирует изменение значения колесиком мыши."""
        if e: 
            e.accept()

    def mousePressEvent(self, ev: Optional[QMouseEvent]) -> None:
        """Разрешает перемещение ползунка только при клике непосредственно на него."""
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
import sys
import logging
from types import TracebackType
from typing import Type
from PyQt6.QtWidgets import QApplication
import view.ui as ui
from controller import controller

def _setup_logging() -> None:
    """Настраивает базовые параметры системного логирования."""
    logging.basicConfig(
        level=logging.WARNING,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def _global_exception_handler(exc_type: Type[BaseException], exc_value: BaseException, exc_traceback: TracebackType | None) -> None:
    """
    Перехватывает и логирует необработанные исключения на уровне приложения.
    
    Args:
        exc_type: Тип исключения.
        exc_value: Значение/сообщение исключения.
        exc_traceback: Объект трассировки стека.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Критическая ошибка приложения:", exc_info=(exc_type, exc_value, exc_traceback))

def main() -> None:
    """Инициализирует компоненты графического интерфейса и запускает главный цикл."""
    _setup_logging()
    sys.excepthook = _global_exception_handler
    
    app = QApplication(sys.argv)
    
    view = ui.SSTView()
    app_controller = controller.SSTController(view)
    
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
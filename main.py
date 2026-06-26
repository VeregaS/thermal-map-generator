import sys
from typing import Any, cast
from PyQt6.QtWidgets import QApplication
import ui

def main() -> None:
    """Инициализирует графическое приложение PyQt6 и запускает цикл SST-приложения."""
    app: QApplication = QApplication(sys.argv)
    window: ui.SSTApp = ui.SSTApp()
    cast(Any, window).show()
    sys.exit(cast(Any, app).exec())

if __name__ == "__main__":
    main()
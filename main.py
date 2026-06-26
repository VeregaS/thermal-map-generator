import sys
from PyQt6.QtWidgets import QApplication
import ui
import controller

def main() -> None:
    """Инициализирует MVC-компоненты приложения и запускает цикл PyQt6."""
    app = QApplication(sys.argv)
    
    view = ui.SSTView()
    _ = controller.SSTController(view)
    
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
from typing import Final

WIDTH_PREVIEW: Final[int] = 500
HEIGHT_PREVIEW: Final[int] = 500

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
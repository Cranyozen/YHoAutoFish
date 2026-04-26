import sys
import os
import logging

# Ensure modules can be found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.dpi import set_process_dpi_awareness

set_process_dpi_awareness()

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from core.paths import resource_path
from gui.app import AppWindow

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(levelname)s] %(name)s: %(message)s",
    )
    logging.info("Starting app...")
    app = QApplication(sys.argv)

    app.setApplicationName("FishingBot")
    app.setWindowIcon(QIcon(resource_path("logo.jpg")))

    logging.info("Creating AppWindow...")
    window = AppWindow()
    logging.info("Showing AppWindow...")
    window.show()
    
    sys.exit(app.exec())

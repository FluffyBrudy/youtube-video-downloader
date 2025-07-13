import sys
from PySide6.QtWidgets import QApplication
from ui import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(500, 200)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QFileDialog,
    QComboBox,
    QApplication,
)
from PySide6.QtCore import QThread, Signal, QPropertyAnimation, Qt
from PySide6.QtGui import QGuiApplication
from downloader import download_video
from typing import Optional
import yt_dlp
import sys


class DownloadThread(QThread):
    progress = Signal(float)
    status = Signal(str)
    formats_ready = Signal(list)

    def __init__(self, url, output_template, format_code=None):
        super().__init__()
        self.url = url
        self.output_template = output_template
        self.format_code = format_code

    def run(self):
        self.status.emit("Loading metadata...")
        try:
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(self.url, download=False)
                formats = info.get("formats", [])
                video_formats = [
                    f
                    for f in formats
                    if f.get("vcodec") != "none" and f.get("acodec") == "none"
                ]
                self.formats_ready.emit(video_formats)

            if self.format_code is None:
                return  # Wait for user to confirm format selection

            def hook(d):
                if d["status"] == "downloading":
                    percent = d.get("_percent_str", "").strip().replace("%", "")
                    try:
                        self.progress.emit(float(percent))
                    except ValueError:
                        pass
                    self.status.emit(f"ETA: {d.get('_eta_str', '...')}")
                elif d["status"] == "finished":
                    self.progress.emit(100.0)
                    self.status.emit("Done")

            download_video(self.url, self.output_template, hook, self.format_code)
        except Exception as e:
            self.status.emit(f"Error: {e}")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YT Downloader")
        self.apply_styles()
        layout = QVBoxLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube video URL")
        layout.addWidget(QLabel("Video URL:"))
        layout.addWidget(self.url_input)

        self.choose_btn = QPushButton("📁 Choose Save Folder")
        self.choose_btn.clicked.connect(self.choose_folder)
        layout.addWidget(self.choose_btn)

        layout.addWidget(QLabel("Choose Quality:"))
        self.quality_box = QComboBox()
        layout.addWidget(self.quality_box)
        self.quality_box.setEnabled(False)

        self.download_btn = QPushButton("⬇️ Start Download")
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        layout.setSpacing(15)
        self.setLayout(layout)

        self.output_folder = ""
        self.thread: Optional[DownloadThread] = None
        self.quality_map = {}
        self.resize_to_screen()
        self._anim = None

    def apply_styles(self):
        self.setStyleSheet(
            """
            QWidget {
                background-color: #121212;
                color: #E0E0E0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 16px;
            }
            QLabel {
                font-size: 18px;
            }
            QLineEdit {
                border: 2px solid #333;
                border-radius: 8px;
                padding: 10px;
                background-color: #1E1E1E;
                color: #E0E0E0;
            }
            QPushButton {
                background-color: #333;
                color: #E0E0E0;
                border: none;
                border-radius: 8px;
                padding: 12px;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton:pressed {
                background-color: #777;
            }
            QComboBox {
                background-color: #1E1E1E;
                border: 2px solid #333;
                border-radius: 8px;
                padding: 8px;
                color: #E0E0E0;
            }
            QProgressBar {
                background-color: #1E1E1E;
                border: 2px solid #333;
                border-radius: 10px;
                height: 25px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #03DAC6;
                border-radius: 10px;
            }
        """
        )

    def resize_to_screen(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        width = int(screen.width() * 0.5)
        height = int(screen.height() * 0.4)
        self.resize(width, height)
        self.move(
            screen.width() // 2 - self.width() // 2,
            screen.height() // 2 - self.height() // 2,
        )

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            self.show_status("Please enter a URL")
            return
        if not self.output_folder:
            self.show_status("Choose save folder")
            return

        template = f"{self.output_folder}/%(title)s.%(ext)s"
        self.quality_box.setEnabled(False)
        self.quality_box.clear()
        self.show_status("Loading metadata...")

        self.thread = DownloadThread(url, template)
        self.thread.progress.connect(self.update_progress)
        self.thread.status.connect(self.update_status)
        self.thread.formats_ready.connect(self.populate_quality_options)
        self.thread.start()

    def populate_quality_options(self, formats):
        self.quality_box.clear()
        self.quality_map = {}

        for f in formats:
            resolution = f"{f.get('height', '?')}p"
            fps = f.get("fps", "")
            size_mb = f.get("filesize", 0)
            size_text = f"{round(size_mb / 1024 / 1024, 1)}MB" if size_mb else "?"
            label = f"{resolution} {fps}fps - {size_text} ({f['format_id']})"
            self.quality_box.addItem(label)
            self.quality_map[label] = f["format_id"]

        self.quality_box.setEnabled(True)
        self.download_btn.setText("⬇️ Confirm Download")
        self.download_btn.clicked.disconnect()
        self.download_btn.clicked.connect(self.confirm_download)

    def confirm_download(self):
        url = self.url_input.text().strip()
        template = f"{self.output_folder}/%(title)s.%(ext)s"
        selected_label = self.quality_box.currentText()
        format_id = self.quality_map.get(selected_label)

        self.thread = DownloadThread(url, template, format_code=format_id)
        self.thread.progress.connect(self.update_progress)
        self.thread.status.connect(self.update_status)
        self.thread.start()

        self.download_btn.setText("⬇️ Start Download")
        self.download_btn.clicked.disconnect()
        self.download_btn.clicked.connect(self.start_download)

    def update_progress(self, percent):
        self.progress_bar.setValue(int(percent))

    def update_status(self, status):
        self.show_status(status)

    def show_status(self, text):
        self.status_label.setText(f"Status: {text}")
        self.fade_in(self.status_label)

    def fade_in(self, widget):
        anim = QPropertyAnimation(widget, b"windowOpacity")
        anim.setDuration(300)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.start()
        self._anim = anim


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

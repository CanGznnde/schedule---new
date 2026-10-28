from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QDate, QIODevice, QUrl, Qt
from PySide6.QtGui import QImage, QTextImageFormat
from PySide6.QtWidgets import (
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import database as db

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
MAX_IMAGE_WIDTH = 640


class LogTextEdit(QTextEdit):
    """Rich text editor for the daily log that accepts pasted, dropped and picked images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.document().setBaseUrl(QUrl.fromLocalFile(str(db.attachments_dir().parent) + "/"))

    def canInsertFromMimeData(self, source):
        return source.hasImage() or self._image_files(source) or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        files = self._image_files(source)
        if files:
            for path in files:
                self.insert_image_file(path)
        elif source.hasImage():
            image = QImage(source.imageData())
            if not image.isNull():
                self._insert_image(self._store_image(image), image)
        elif source.hasText():
            # Paste text only, so formatting from other apps does not leak into the log.
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)

    @staticmethod
    def _image_files(source):
        paths = [Path(url.toLocalFile()) for url in source.urls() if url.isLocalFile()]
        return [p for p in paths if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file()]

    @staticmethod
    def _store_image(image):
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        return db.store_attachment(bytes(data), ".png")

    def insert_image_file(self, path):
        path = Path(path)
        image = QImage(str(path))
        if image.isNull():
            return False
        self._insert_image(db.store_attachment(path.read_bytes(), path.suffix), image)
        return True

    def _insert_image(self, relative_path, image):
        width = min(image.width(), MAX_IMAGE_WIDTH)
        fmt = QTextImageFormat()
        fmt.setName(relative_path)
        fmt.setWidth(width)
        fmt.setHeight(image.height() * width / image.width())
        cursor = self.textCursor()
        cursor.insertImage(fmt)
        cursor.insertBlock()
        self.setTextCursor(cursor)

    def set_log(self, content):
        if db.is_rich_log(content):
            self.setHtml(content)
        else:
            self.setPlainText(content)

    def log_content(self):
        """HTML when the log holds images, otherwise plain text (keeps text-only logs unchanged)."""
        html = self.toHtml()
        return html if "<img" in html else self.toPlainText()


class DailyLogView(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setSpacing(10)

        header = QHBoxLayout()

        title = QLabel("Daily Log: ")
        title.setObjectName("pageTitle")
        header.addWidget(title)

        self.prev_btn = QPushButton("<")
        self.prev_btn.setFixedWidth(30)
        self.prev_btn.clicked.connect(self.prev_day)
        header.addWidget(self.prev_btn)

        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDate(QDate.currentDate())
        self.date_picker.setObjectName("dailyDate")

        self.date_picker.dateChanged.connect(self.load_log)
        header.addWidget(self.date_picker)

        self.next_btn = QPushButton(">")
        self.next_btn.setFixedWidth(30)
        self.next_btn.clicked.connect(self.next_day)
        header.addWidget(self.next_btn)

        self.today_btn = QPushButton("Jump to Today")
        self.today_btn.clicked.connect(lambda: self.date_picker.setDate(QDate.currentDate()))
        header.addWidget(self.today_btn)

        header.addStretch()

        self.image_btn = QPushButton("Add Image...")
        self.image_btn.setToolTip("Insert an image into this day's log (you can also paste or drag images in)")
        self.image_btn.clicked.connect(self.add_images)
        header.addWidget(self.image_btn)
        root.addLayout(header)

        self.text_area = LogTextEdit()
        self.text_area.setPlaceholderText("Capture progress, blockers, and notes from the day...\nTip: paste a screenshot or drag an image here.")
        self.text_area.textChanged.connect(self.auto_save)
        root.addWidget(self.text_area)

        row = QHBoxLayout()
        self.status = QLabel("")
        row.addWidget(self.status)
        row.addStretch()
        root.addLayout(row)

        self.load_log()

    def load_log(self):
        self.text_area.blockSignals(True)
        date_str = self.date_picker.date().toString(Qt.DateFormat.ISODate)
        self.text_area.set_log(db.get_log(date_str))
        self.text_area.blockSignals(False)
        self.status.setText("Log loaded.")

    def auto_save(self):
        date_str = self.date_picker.date().toString(Qt.DateFormat.ISODate)
        db.save_log(date_str, self.text_area.log_content())
        self.status.setText("Autosaved")

    def add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Image", "", IMAGE_FILTER)
        failed = [Path(p).name for p in paths if not self.text_area.insert_image_file(p)]
        if failed:
            QMessageBox.warning(self, "Add Image", "Could not read: " + ", ".join(failed))

    def prev_day(self):
        self.date_picker.setDate(self.date_picker.date().addDays(-1))

    def next_day(self):
        self.date_picker.setDate(self.date_picker.date().addDays(1))

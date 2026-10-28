from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDateEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import database as db


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
        root.addLayout(header)

        self.text_area = QTextEdit()
        self.text_area.setPlaceholderText("Capture progress, blockers, and notes from the day...")
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
        self.text_area.setText(db.get_log(date_str))
        self.text_area.blockSignals(False)
        self.status.setText("Log loaded.")

    def auto_save(self):
        date_str = self.date_picker.date().toString(Qt.DateFormat.ISODate)
        db.save_log(date_str, self.text_area.toPlainText())
        self.status.setText("Autosaved")

    def prev_day(self):
        self.date_picker.setDate(self.date_picker.date().addDays(-1))
        
    def next_day(self):
        self.date_picker.setDate(self.date_picker.date().addDays(1))

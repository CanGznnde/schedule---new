from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import database as db


class StatCard(QFrame):
    def __init__(self, label, value_getter):
        super().__init__()
        self.value_getter = value_getter
        self.setObjectName("statCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.value_label = QLabel("0")
        self.value_label.setObjectName("statValue")
        layout.addWidget(self.value_label)

        title = QLabel(label)
        title.setObjectName("statTitle")
        layout.addWidget(title)

        self.refresh()

    def refresh(self):
        self.value_label.setText(str(self.value_getter()))


class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        self.cards = []

        root = QVBoxLayout(self)
        root.setSpacing(12)

        heading = QLabel("Overview")
        heading.setObjectName("pageTitle")
        root.addWidget(heading)

        subtitle = QLabel("Quick pulse of your workload and priorities.")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(subtitle)

        self.meeting_alert = QLabel("")
        self.meeting_alert.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 15px; margin-top: 5px;")
        self.meeting_alert.setVisible(False)
        root.addWidget(self.meeting_alert)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        root.addLayout(grid)

        self.stats = {}
        self._reload_stats()

        definitions = [
            ("Projects", "projects"),
            ("All Tasks", "total_tasks"),
            ("Open", "open_tasks"),
            ("Completed", "completed_tasks"),
            ("Due Today", "due_today"),
            ("Overdue", "overdue"),
        ]

        for idx, (label, key) in enumerate(definitions):
            card = StatCard(label, lambda k=key: self.stats.get(k, 0))
            grid.addWidget(card, idx // 3, idx % 3)
            self.cards.append(card)

        root.addWidget(QLabel("Upcoming Deadlines"))
        self.upcoming = QListWidget()
        root.addWidget(self.upcoming)
        self.refresh()

    def _reload_stats(self):
        self.stats = db.get_dashboard_stats()

    def refresh(self):
        self._reload_stats()
        for card in self.cards:
            card.refresh()

        meeting = db.get_upcoming_meeting()
        if meeting:
            title, meeting_deadline, proj_name = meeting
            d = QDate.fromString(meeting_deadline, Qt.DateFormat.ISODate)
            if d.isValid():
                days_left = QDate.currentDate().daysTo(d)
                if days_left < 0:
                    day_text = f"{-days_left} days overdue"
                elif days_left == 0:
                    day_text = "today"
                elif days_left == 1:
                    day_text = "1 day left"
                else:
                    day_text = f"{days_left} days left"
                self.meeting_alert.setText(f"Upcoming Meeting: {title} ({proj_name}) - {day_text}")
            else:
                self.meeting_alert.setText(f"Upcoming Meeting: {title} ({proj_name}) - {meeting_deadline}")
            self.meeting_alert.setVisible(True)
        else:
            self.meeting_alert.setVisible(False)

        self.upcoming.clear()
        deadlines = db.get_upcoming_deadlines()[:10]
        if not deadlines:
            self.upcoming.addItem("No upcoming deadlines. Nice work.")
            return

        today_str = QDate.currentDate().toString(Qt.DateFormat.ISODate)
        for title, deadline in deadlines:
            item = QListWidgetItem(f"{deadline}  -  {title}")
            if deadline == today_str:
                item.setForeground(QColor("#e74c3c"))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.upcoming.addItem(item)


class ProjectsOverviewView(QWidget):
    def __init__(self, open_project_callback=None):
        super().__init__()
        self.open_project_callback = open_project_callback

        root = QVBoxLayout(self)
        root.setSpacing(10)

        heading = QLabel("Projects")
        heading.setObjectName("pageTitle")
        root.addWidget(heading)

        subtitle = QLabel("Project blocks with quick status information.")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(subtitle)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.scroll.setWidget(self.container)

        self.refresh()

    def refresh(self):
        while self.grid.count() > 0:
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        projects = db.get_projects()
        if not projects:
            empty = QLabel("No projects yet.")
            self.grid.addWidget(empty, 0, 0)
            return

        columns = 2
        today = QDate.currentDate().toString(Qt.DateFormat.ISODate)

        for idx, (project_id, project_name, start_date, end_date) in enumerate(projects):
            tasks = db.get_tasks(project_id)
            total = len(tasks)
            done = len([row for row in tasks if row[5]])
            open_count = total - done
            due_today = len([row for row in tasks if row[2] == today and not row[5]])

            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(6)

            title = QLabel(project_name)
            title.setObjectName("pageTitle")
            title.setStyleSheet("font-size: 16px;")
            card_layout.addWidget(title)

            date_text = "No project date range"
            if start_date and end_date:
                date_text = f"{start_date} to {end_date}"
            elif start_date:
                date_text = f"Starts {start_date}"
            card_layout.addWidget(QLabel(date_text))

            card_layout.addWidget(QLabel(f"Tasks: {open_count} open / {total} total"))
            card_layout.addWidget(QLabel(f"Due today: {due_today}"))

            open_btn = QPushButton("Open Project")
            if self.open_project_callback is not None:
                open_btn.clicked.connect(lambda _=False, pid=project_id: self.open_project_callback(pid))
            card_layout.addWidget(open_btn)

            row = idx // columns
            col = idx % columns
            self.grid.addWidget(card, row, col)

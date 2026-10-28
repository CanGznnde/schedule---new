from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

import database as db
from .theme import CALENDAR_PALETTE
from .calendar_widget import TaskCalendarWidget


class CalendarView(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setSpacing(10)

        heading = QLabel("Calendar and Deadlines")
        heading.setObjectName("pageTitle")
        root.addWidget(heading)

        self.calendar = TaskCalendarWidget()
        self.calendar.selectionChanged.connect(self.load_selected_day)
        root.addWidget(self.calendar)

        root.addWidget(QLabel("Tasks on Selected Date"))
        self.selected_day_tasks = QListWidget()
        root.addWidget(self.selected_day_tasks)

        root.addWidget(QLabel("Upcoming Deadlines"))
        self.deadlines_list = QListWidget()
        root.addWidget(self.deadlines_list)

        self.refresh()

    def load_selected_day(self):
        self.selected_day_tasks.clear()
        date_str = self.calendar.selectedDate().toString(Qt.DateFormat.ISODate)
        rows = db.get_tasks_for_date(date_str)
        if not rows:
            self.selected_day_tasks.addItem("No tasks for selected day.")
            return

        for title, project, start_time, end_time, completed, _ in rows:
            status = "Done" if completed else "Open"
            time_text = ""
            if start_time and end_time:
                time_text = f" ({start_time}-{end_time})"
            elif start_time:
                time_text = f" ({start_time})"
            self.selected_day_tasks.addItem(f"{title}{time_text}  -  {project}  -  {status}")

    def refresh(self):
        self.deadlines_list.clear()
        today_str = QDate.currentDate().toString(Qt.DateFormat.ISODate)
        for title, deadline in db.get_upcoming_deadlines():
            item = QListWidgetItem(f"{deadline}  -  {title}")
            if deadline == today_str:
                item.setForeground(QColor("#e74c3c"))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.deadlines_list.addItem(item)
            
        task_data = {}
        for title, start_date, deadline, project_name, start_time, end_time, completed, _, project_id, work_package in db.get_all_tasks():
            end_d = QDate.fromString(deadline, Qt.DateFormat.ISODate)
            if not end_d.isValid():
                continue
            start_d = QDate.fromString(start_date, Qt.DateFormat.ISODate) if start_date else end_d
            if not start_d.isValid():
                start_d = end_d
                
            if not (work_package and work_package.lower() == "meeting"):
                continue
                
            color = CALENDAR_PALETTE[project_id % len(CALENDAR_PALETTE)]
            if completed:
                color = "#95a5a6"
                
            curr_d = start_d
            while curr_d <= end_d:
                if curr_d not in task_data:
                    task_data[curr_d] = []
                task_data[curr_d].append({
                    "title": title,
                    "project": project_name,
                    "color": color,
                    "completed": completed,
                    "start_time": start_time,
                    "end_time": end_time
                })
                curr_d = curr_d.addDays(1)
        self.calendar.set_tasks(task_data)

        self.load_selected_day()

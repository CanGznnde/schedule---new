from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QDateEdit,
    QCheckBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QDialog,
)

import database as db
from .theme import CALENDAR_PALETTE, PRIORITY_LABELS, PRIORITY_COLORS
from .calendar_widget import TaskCalendarWidget
from .dialogs import TaskDetailsDialog
from .dialogs import TaskEditDialog
from .gantt import GanttTab


class TaskView(QWidget):
    def __init__(self, project_id, refresh_all_callback):
        super().__init__()
        self.project_id = project_id
        self.refresh_all_callback = refresh_all_callback

        root = QVBoxLayout(self)
        root.setSpacing(10)

        title = QLabel("Project Tasks")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        self.tabs.addTab(tab1, "List && Calendar")

        self.gantt = GanttTab(self.update_from_gantt)
        self.tabs.addTab(self.gantt, "Gantt Chart")

        input_layout = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Add a new task...  (Ctrl+N)")
        self.task_input.returnPressed.connect(self.add_task)

        self.priority_input = QComboBox()
        self.priority_input.addItems(PRIORITY_LABELS)
        self.priority_input.setToolTip("Priority")

        self.work_package_input = QComboBox()
        self.work_package_input.setEditable(True)
        self.work_package_input.setPlaceholderText("Work Package (Optional)")

        self.start_date_picker = QDateEdit()
        self.start_date_picker.setCalendarPopup(True)
        self.start_date_picker.setDate(QDate.currentDate())

        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDate(QDate.currentDate())

        self.with_time_checkbox = QCheckBox("Add time range")
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm")
        self.start_time_edit.setTime(QTime(9, 0))
        self.start_time_edit.setEnabled(False)

        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm")
        self.end_time_edit.setTime(QTime(10, 0))
        self.end_time_edit.setEnabled(False)

        self.with_time_checkbox.toggled.connect(self.start_time_edit.setEnabled)
        self.with_time_checkbox.toggled.connect(self.end_time_edit.setEnabled)

        add_btn = QPushButton("Add Task")
        add_btn.clicked.connect(self.add_task)

        input_layout.addWidget(self.task_input, 1)
        input_layout.addWidget(self.priority_input)
        input_layout.addWidget(add_btn)
        tab1_layout.addLayout(input_layout)

        options_layout = QHBoxLayout()
        options_layout.addWidget(self.work_package_input, 1)
        options_layout.addWidget(self.start_date_picker)
        label = QLabel("-")
        options_layout.addWidget(label)
        options_layout.addWidget(self.date_picker)
        options_layout.addWidget(self.with_time_checkbox)
        options_layout.addWidget(self.start_time_edit)
        options_layout.addWidget(self.end_time_edit)
        tab1_layout.addLayout(options_layout)

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter tasks in this project...")
        self.search.textChanged.connect(self.apply_filters)

        self.filter_box = QComboBox()
        self.filter_box.addItems(["All", "Open", "Completed", "Due Today", "Overdue", "High Priority"])
        self.filter_box.currentIndexChanged.connect(self.apply_filters)

        controls.addWidget(self.search)
        controls.addWidget(self.filter_box)
        tab1_layout.addLayout(controls)

        self.task_list = QListWidget()
        self.task_list.itemChanged.connect(self.update_task_status)
        self.task_list.itemDoubleClicked.connect(self.open_task_details)
        self.task_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self.show_context_menu)
        tab1_layout.addWidget(self.task_list)

        action_row = QHBoxLayout()
        self.finish_btn = QPushButton("Finish Selected")
        self.finish_btn.clicked.connect(self.finish_selected_task)
        self.finish_btn.setEnabled(False)

        self.archive_btn = QPushButton("Archive Completed")
        self.archive_btn.setToolTip("Move all completed tasks of this project to the Archive")
        self.archive_btn.clicked.connect(self.archive_completed)

        self.delete_btn = QPushButton("Delete Selected / Checked")
        self.delete_btn.clicked.connect(self.delete_selected_task)
        self.delete_btn.setEnabled(False)
        self.task_list.currentItemChanged.connect(self.on_current_item_changed)

        action_row.addWidget(self.finish_btn)
        action_row.addWidget(self.archive_btn)
        action_row.addStretch()
        action_row.addWidget(self.delete_btn)
        tab1_layout.addLayout(action_row)

        tab1_layout.addWidget(QLabel("Project Calendar"))
        self.project_calendar = TaskCalendarWidget()
        self.project_calendar.selectionChanged.connect(self.load_project_day_tasks)
        tab1_layout.addWidget(self.project_calendar)

        tab1_layout.addWidget(QLabel("Tasks for Selected Project Date"))
        self.project_day_tasks = QListWidget()
        tab1_layout.addWidget(self.project_day_tasks)

        self.rows = []
        self.load_tasks()

    def update_from_gantt(self):
        self.load_tasks()
        self.refresh_all_callback()

    def open_task_details(self, item):
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if task_id is None:
            return
        title = item.text().split(" (Date:")[0]
        title = title.replace(" (☑)", "") # Strip icon securely
        for label in PRIORITY_LABELS[1:]:
            title = title.removeprefix(f"[{label}] ")
        dlg = TaskDetailsDialog(task_id, title, self)
        dlg.exec()
        self.load_tasks()
        self.refresh_all_callback()
        
    def show_context_menu(self, pos):
        item = self.task_list.itemAt(pos)
        if not item: return
        
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        edit_action = menu.addAction("Edit Task Details")
        edit_action.triggered.connect(lambda: self.edit_task(item))
        archive_action = menu.addAction("Archive Task")
        archive_action.triggered.connect(lambda: self.archive_task(item))
        menu.exec(self.task_list.viewport().mapToGlobal(pos))
        
    def edit_task(self, item):
        task_id = item.data(Qt.ItemDataRole.UserRole)
        dlg = TaskEditDialog(task_id, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_tasks()
            self.refresh_all_callback()

    def focus_new_task(self):
        self.tabs.setCurrentIndex(0)
        self.task_input.setFocus()

    def load_tasks(self):
        self.rows = db.get_tasks(self.project_id)
        self.extras = db.get_task_extras(self.project_id)
        self.subtask_counts = db.get_subtask_counts(self.project_id)
        
        wps = set(r[7] for r in self.rows if r[7])
        current_wp = self.work_package_input.currentText()
        self.work_package_input.clear()
        self.work_package_input.addItems(sorted(list(wps)))
        self.work_package_input.setCurrentText(current_wp)
        
        task_data = {}
        gantt_data = []
        for task_id, title, start_date, deadline, start_time, end_time, completed, work_package in self.rows:
            end_d = QDate.fromString(deadline, Qt.DateFormat.ISODate)
            if not end_d.isValid():
                continue
            start_d = QDate.fromString(start_date, Qt.DateFormat.ISODate) if start_date else end_d
            if not start_d.isValid():
                start_d = end_d
                
            gantt_data.append({
                "id": task_id,
                "title": title,
                "start_date": start_d.toString(Qt.DateFormat.ISODate),
                "deadline": end_d.toString(Qt.DateFormat.ISODate),
                "work_package": work_package or "General",
                "has_subtasks": self.subtask_counts.get(task_id, 0) > 0
            })
            
            if not (work_package and work_package.lower() == "meeting"):
                continue
                
            color = CALENDAR_PALETTE[self.project_id % len(CALENDAR_PALETTE)]
            if completed:
                color = "#95a5a6" # Grey out completed calendar rings
                
            curr_d = start_d
            while curr_d <= end_d:
                if curr_d not in task_data:
                    task_data[curr_d] = []
                task_data[curr_d].append({
                    "title": title,
                    "color": color,
                    "completed": completed,
                    "start_time": start_time,
                    "end_time": end_time
                })
                curr_d = curr_d.addDays(1)
        
        project = db.get_project(self.project_id)
        project_start = project[2] if project else None

        self.gantt.load_tasks(gantt_data, project_start)
        self.project_calendar.set_tasks(task_data)

        self.apply_filters()
        self.load_project_day_tasks()

    def apply_filters(self):
        self.task_list.blockSignals(True)
        self.task_list.clear()

        query = self.search.text().strip().lower()
        mode = self.filter_box.currentText()
        today = QDate.currentDate().toString(Qt.DateFormat.ISODate)

        for task_id, title, start_date, deadline, start_time, end_time, completed, _ in self.rows:
            if query and query not in title.lower():
                continue

            if mode == "Open" and completed:
                continue
            if mode == "Completed" and not completed:
                continue
            if mode == "Due Today" and deadline != today:
                continue
            if mode == "Overdue" and (completed or deadline >= today):
                continue
            priority, notes = self.extras.get(task_id, (0, ""))
            if mode == "High Priority" and priority != 3:
                continue

            time_text = ""
            if start_time and end_time:
                time_text = f" {start_time}-{end_time}"
            elif start_time:
                time_text = f" {start_time}"

            checklist_indicator = " (☑)" if self.subtask_counts.get(task_id, 0) > 0 else ""
            date_str = f"{start_date} to {deadline}" if start_date and start_date != deadline else deadline
            priority_text = f"[{PRIORITY_LABELS[priority]}] " if priority else ""
            item = QListWidgetItem(f"{priority_text}{title}{checklist_indicator} (Date: {date_str}{time_text})")
            if priority in PRIORITY_COLORS and not completed:
                item.setForeground(QColor(PRIORITY_COLORS[priority]))
            if notes:
                item.setToolTip(notes)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(Qt.CheckState.Checked if completed else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, task_id)
            font = item.font()
            font.setStrikeOut(bool(completed))
            item.setFont(font)
            self.task_list.addItem(item)

        if self.task_list.count() == 0:
            hint = "No tasks yet. Type a title above and press Enter." if not self.rows else "No tasks match the current filter."
            placeholder = QListWidgetItem(hint)
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.task_list.addItem(placeholder)

        self.task_list.blockSignals(False)

    def add_task(self):
        title = self.task_input.text().strip()
        if not title:
            return

        deadline = self.date_picker.date().toString(Qt.DateFormat.ISODate)
        start_date = self.start_date_picker.date().toString(Qt.DateFormat.ISODate)
        
        if self.date_picker.date() < self.start_date_picker.date():
            QMessageBox.warning(self, "Invalid Date", "End date must be on or after start date.")
            return

        start_time = None
        end_time = None
        if self.with_time_checkbox.isChecked():
            start_time = self.start_time_edit.time().toString("HH:mm")
            end_time = self.end_time_edit.time().toString("HH:mm")
            if self.end_time_edit.time() < self.start_time_edit.time():
                QMessageBox.warning(self, "Invalid Time", "End time must be after start time.")
                return

        wp = self.work_package_input.currentText().strip()

        db.add_task(self.project_id, title, start_date, deadline, start_time, end_time, completed=0, work_package=wp,
                    priority=self.priority_input.currentIndex())
        self.priority_input.setCurrentIndex(0)
        self.task_input.clear()
        self.load_tasks()
        self.refresh_all_callback()

    def update_task_status(self, item):
        task_id = item.data(Qt.ItemDataRole.UserRole)
        completed = 1 if item.checkState() == Qt.CheckState.Checked else 0
        db.toggle_task_completion(task_id, completed)
        self.load_tasks()
        self.refresh_all_callback()

    def finish_selected_task(self):
        current = self.task_list.currentItem()
        if not current:
            return

        task_id = current.data(Qt.ItemDataRole.UserRole)
        db.toggle_task_completion(task_id, 1)
        self.load_tasks()
        self.refresh_all_callback()

    def archive_task(self, item):
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if task_id is None:
            return
        db.set_task_archived(task_id, True)
        self.load_tasks()
        self.refresh_all_callback()

    def archive_completed(self):
        if not db.archive_completed_tasks(self.project_id):
            QMessageBox.information(self, "Archive Completed", "There are no completed tasks to archive.")
            return
        self.load_tasks()
        self.refresh_all_callback()

    def delete_selected_task(self):
        ids_to_delete = set()

        current = self.task_list.currentItem()
        if current:
            ids_to_delete.add(current.data(Qt.ItemDataRole.UserRole))

        for idx in range(self.task_list.count()):
            item = self.task_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                ids_to_delete.add(item.data(Qt.ItemDataRole.UserRole))

        if not ids_to_delete:
            QMessageBox.information(self, "Delete Task", "Select or check at least one task to delete.")
            return

        noun = "task" if len(ids_to_delete) == 1 else "tasks"
        answer = QMessageBox.question(
            self,
            "Delete Task",
            f"Delete {len(ids_to_delete)} {noun}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        for task_id in ids_to_delete:
            db.delete_task(task_id)

        self.load_tasks()
        self.refresh_all_callback()

    def on_current_item_changed(self, current, _previous):
        enabled = current is not None
        self.finish_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

    def load_project_day_tasks(self):
        self.project_day_tasks.clear()
        date_str = self.project_calendar.selectedDate().toString(Qt.DateFormat.ISODate)
        rows = db.get_tasks_for_project_date(self.project_id, date_str)
        if not rows:
            self.project_day_tasks.addItem("No tasks for this project on selected day.")
            return

        for _, title, start_time, end_time, completed, _ in rows:
            status = "Done" if completed else "Open"
            time_text = ""
            if start_time and end_time:
                time_text = f" ({start_time}-{end_time})"
            elif start_time:
                time_text = f" ({start_time})"
            self.project_day_tasks.addItem(f"{title}{time_text}  -  {status}")

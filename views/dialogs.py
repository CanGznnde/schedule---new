from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QDateEdit,
    QTimeEdit,
    QTextEdit,
    QVBoxLayout,
    QDialog,
    QFormLayout,
)

from .theme import PRIORITY_LABELS


class TaskDetailsDialog(QDialog):
    def __init__(self, task_id, task_title, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.setWindowTitle("Task Checklist")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        title_lbl = QLabel(f"<b>{task_title}</b> Checklists")
        title_lbl.setStyleSheet("font-size: 16px;")
        layout.addWidget(title_lbl)
        
        input_layout = QHBoxLayout()
        self.subtask_input = QLineEdit()
        self.subtask_input.setPlaceholderText("Add a checklist item...")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_subtask)
        input_layout.addWidget(self.subtask_input)
        input_layout.addWidget(add_btn)
        layout.addLayout(input_layout)
        
        self.subtask_list = QListWidget()
        self.subtask_list.itemChanged.connect(self.update_subtask_status)
        layout.addWidget(self.subtask_list)
        
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected)
        layout.addWidget(delete_btn)
        
        self.load_subtasks()
        
    def load_subtasks(self):
        self.subtask_list.blockSignals(True)
        self.subtask_list.clear()
        import database as db
        rows = db.get_subtasks(self.task_id)
        for sid, title, completed in rows:
            item = QListWidgetItem(title)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(Qt.CheckState.Checked if completed else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            
            font = item.font()
            font.setStrikeOut(bool(completed))
            item.setFont(font)
            
            self.subtask_list.addItem(item)
        self.subtask_list.blockSignals(False)
        
    def add_subtask(self):
        title = self.subtask_input.text().strip()
        if not title: return
        import database as db
        db.add_subtask(self.task_id, title)
        self.subtask_input.clear()
        self.load_subtasks()
        
    def update_subtask_status(self, item):
        sid = item.data(Qt.ItemDataRole.UserRole)
        completed = 1 if item.checkState() == Qt.CheckState.Checked else 0
        import database as db
        db.toggle_subtask(sid, completed)
        self.load_subtasks()
        
    def delete_selected(self):
        current = self.subtask_list.currentItem()
        if not current: return
        sid = current.data(Qt.ItemDataRole.UserRole)
        import database as db
        db.delete_subtask(sid)
        self.load_subtasks()

class TaskEditDialog(QDialog):
    def __init__(self, task_id, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.setWindowTitle("Edit Task")
        self.resize(420, 400)
        
        import database as db
        task = db.get_task(task_id)
        if not task:
            self.reject()
            return
            
        layout = QFormLayout(self)
        
        self.title_input = QLineEdit(task[2])
        layout.addRow("Title:", self.title_input)
        
        self.wp_input = QLineEdit(task[8] if task[8] else "")
        self.wp_input.setPlaceholderText("Optional Work Package")
        layout.addRow("Work Package:", self.wp_input)
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        if task[3]: 
            self.start_date.setDate(QDate.fromString(task[3], Qt.DateFormat.ISODate))
        else:
            self.start_date.setDate(QDate.currentDate())
        layout.addRow("Start Date:", self.start_date)
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        if task[4]: 
            self.end_date.setDate(QDate.fromString(task[4], Qt.DateFormat.ISODate))
        else:
            self.end_date.setDate(QDate.currentDate())
        layout.addRow("Deadline:", self.end_date)
        
        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        if task[5]: self.start_time.setTime(QTime.fromString(task[5], "HH:mm"))
        layout.addRow("Start Time:", self.start_time)
        
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        if task[6]: self.end_time.setTime(QTime.fromString(task[6], "HH:mm"))
        layout.addRow("End Time:", self.end_time)

        self.priority_input = QComboBox()
        self.priority_input.addItems(PRIORITY_LABELS)
        self.priority_input.setCurrentIndex(max(0, min(task[9], len(PRIORITY_LABELS) - 1)))
        layout.addRow("Priority:", self.priority_input)

        self.notes_input = QTextEdit()
        self.notes_input.setAcceptRichText(False)
        self.notes_input.setPlaceholderText("Notes, links, details...")
        self.notes_input.setPlainText(task[10])
        layout.addRow("Notes:", self.notes_input)
        
        from PySide6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save_task)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def save_task(self):
        import database as db
        db.update_task_details(
            self.task_id,
            self.title_input.text().strip() or "Untitled Task",
            self.start_date.date().toString(Qt.DateFormat.ISODate),
            self.end_date.date().toString(Qt.DateFormat.ISODate),
            self.start_time.time().toString("HH:mm"),
            self.end_time.time().toString("HH:mm"),
            self.wp_input.text().strip(),
            self.priority_input.currentIndex(),
            self.notes_input.toPlainText().strip(),
        )
        self.accept()

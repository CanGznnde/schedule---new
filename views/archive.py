from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import database as db


class ArchiveView(QWidget):
    """Lists archived projects and tasks so they can be restored or deleted for good."""

    def __init__(self, refresh_callback):
        super().__init__()
        self.refresh_callback = refresh_callback

        root = QVBoxLayout(self)
        root.setSpacing(10)

        title = QLabel("Archive")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        subtitle = QLabel("Archived items are hidden everywhere else and left out of search. Restore them any time.")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(subtitle)

        self.project_list = self._add_section(root, "Archived projects", self.restore_project, self.delete_project)
        self.task_list = self._add_section(root, "Archived tasks", self.restore_task, self.delete_task)

        self.refresh()

    def _add_section(self, root, heading, restore_slot, delete_slot):
        root.addWidget(QLabel(heading))
        list_widget = QListWidget()
        root.addWidget(list_widget, 1)

        buttons = QHBoxLayout()
        restore_btn = QPushButton("Restore")
        restore_btn.clicked.connect(restore_slot)
        delete_btn = QPushButton("Delete permanently")
        delete_btn.clicked.connect(delete_slot)
        buttons.addWidget(restore_btn)
        buttons.addStretch()
        buttons.addWidget(delete_btn)
        root.addLayout(buttons)
        return list_widget

    def refresh(self):
        self.project_list.clear()
        for project_id, name, start_date, end_date, task_count in db.get_archived_projects():
            noun = "task" if task_count == 1 else "tasks"
            item = QListWidgetItem(f"{name}  ({task_count} {noun})")
            item.setData(Qt.ItemDataRole.UserRole, project_id)
            self.project_list.addItem(item)
        self._add_placeholder_if_empty(self.project_list, "No archived projects. Right-click a project in the sidebar to archive it.")

        self.task_list.clear()
        for task_id, title, deadline, completed, _, project_name in db.get_archived_tasks():
            status = "done" if completed else f"due {deadline}"
            item = QListWidgetItem(f"{title}  -  {project_name}  ({status})")
            item.setData(Qt.ItemDataRole.UserRole, task_id)
            self.task_list.addItem(item)
        self._add_placeholder_if_empty(self.task_list, "No archived tasks. Use \"Archive Completed\" on a project's task list.")

    @staticmethod
    def _add_placeholder_if_empty(list_widget, text):
        if list_widget.count() == 0:
            placeholder = QListWidgetItem(text)
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            list_widget.addItem(placeholder)

    @staticmethod
    def _selected_id(list_widget):
        item = list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _confirm_delete(self, what):
        answer = QMessageBox.question(
            self,
            "Delete permanently",
            f"Permanently delete this {what}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def restore_project(self):
        project_id = self._selected_id(self.project_list)
        if project_id is not None:
            db.set_project_archived(project_id, False)
            self.refresh_callback()

    def delete_project(self):
        project_id = self._selected_id(self.project_list)
        if project_id is not None and self._confirm_delete("project and all its tasks"):
            db.delete_project(project_id)
            self.refresh_callback()

    def restore_task(self):
        task_id = self._selected_id(self.task_list)
        if task_id is not None:
            db.set_task_archived(task_id, False)
            self.refresh_callback()

    def delete_task(self):
        task_id = self._selected_id(self.task_list)
        if task_id is not None and self._confirm_delete("task"):
            db.delete_task(task_id)
            self.refresh_callback()

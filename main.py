import datetime
import sys

from PySide6.QtCore import QDate, QSettings, Qt
from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
import database as db
from views import CalendarView, DailyLogView, DashboardView, ProjectsOverviewView, TaskView


THEMES = {
    "light": {
        "win_a": "#f6f7f4", "win_b": "#eef3f6", "text": "#1f2933", "panel": "#ffffff",
        "border": "#d6dde6", "sel": "#d3e8f0", "sel_text": "#13222e", "button": "#1f6f8b",
        "button_hover": "#1b617a", "input_border": "#ccd5df", "title": "#0f2836",
        "subtitle": "#5b6b79", "card_border": "#d9e1e8", "daily_bg": "#eef3f6",
    },
    "dark": {
        "win_a": "#1b1f24", "win_b": "#20262c", "text": "#dde3e8", "panel": "#262c33",
        "border": "#38414a", "sel": "#2f4a5a", "sel_text": "#f0f4f7", "button": "#2a8aad",
        "button_hover": "#3299bf", "input_border": "#424c56", "title": "#f0f4f7",
        "subtitle": "#9aa7b3", "card_border": "#38414a", "daily_bg": "#262c33",
    },
}

STYLE_TEMPLATE = """
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 @win_a@, stop:1 @win_b@);
}
QWidget {
    color: @text@;
    font-family: "Segoe UI";
    font-size: 13px;
}
QTreeWidget {
    background: @panel@;
    border: 1px solid @border@;
    border-radius: 10px;
    padding: 6px;
}
QTreeWidget::item {
    border-radius: 8px;
    padding: 9px;
    margin: 2px 0;
}
QTreeWidget::item:selected {
    background: @sel@;
    color: @sel_text@;
}
QPushButton {
    background: @button@;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background: @button_hover@;
}
QLineEdit, QTextEdit, QDateEdit, QComboBox {
    background: @panel@;
    border: 1px solid @input_border@;
    border-radius: 8px;
    padding: 7px;
}
QDateEdit#dailyDate {
    font-size: 20px;
    font-weight: 700;
    color: @title@;
    background: @daily_bg@;
    border: 1px solid @card_border@;
    border-radius: 8px;
    padding: 4px;
}
QLabel#pageTitle {
    font-size: 20px;
    font-weight: 700;
    color: @title@;
}
QLabel#pageSubtitle {
    color: @subtitle@;
}
QFrame#statCard {
    background: @panel@;
    border: 1px solid @card_border@;
    border-radius: 12px;
}
QLabel#statValue {
    font-size: 24px;
    font-weight: 700;
    color: @title@;
}
QLabel#statTitle {
    color: @subtitle@;
    font-size: 12px;
    font-weight: 600;
}
QLabel#emptyHint {
    color: @subtitle@;
}
"""


def build_style(theme="light"):
    style = STYLE_TEMPLATE
    for key, value in THEMES[theme].items():
        style = style.replace(f"@{key}@", value)
    return style


APP_STYLE = build_style("light")


def apply_theme(app, dark):
    app.setStyle("Fusion")
    if dark:
        palette = QPalette()
        roles = {
            QPalette.ColorRole.Window: "#1b1f24", QPalette.ColorRole.WindowText: "#dde3e8",
            QPalette.ColorRole.Base: "#262c33", QPalette.ColorRole.AlternateBase: "#2b323a",
            QPalette.ColorRole.Text: "#dde3e8", QPalette.ColorRole.Button: "#2b323a",
            QPalette.ColorRole.ButtonText: "#dde3e8", QPalette.ColorRole.Highlight: "#2a8aad",
            QPalette.ColorRole.HighlightedText: "#ffffff", QPalette.ColorRole.ToolTipBase: "#2b323a",
            QPalette.ColorRole.ToolTipText: "#dde3e8", QPalette.ColorRole.PlaceholderText: "#7d8994",
            QPalette.ColorRole.Link: "#5cb8e0",
        }
        for role, color in roles.items():
            palette.setColor(role, QColor(color))
        app.setPalette(palette)
    else:
        app.setPalette(app.style().standardPalette())
    app.setStyleSheet(build_style("dark" if dark else "light"))


class SearchDialog(QDialog):
    """Global search over tasks (title, notes, work package, project) and daily logs."""

    def __init__(self, navigate_callback, parent=None):
        super().__init__(parent)
        self.navigate_callback = navigate_callback
        self.setWindowTitle("Search")
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Search tasks, notes, projects and daily logs...")
        self.query_input.textChanged.connect(self.run_search)
        layout.addWidget(self.query_input)

        self.results = QListWidget()
        self.results.itemActivated.connect(self.open_result)
        self.results.itemDoubleClicked.connect(self.open_result)
        layout.addWidget(self.results, 1)

        self.hint = QLabel("Type to search. Press Enter or double-click a result to open it.")
        self.hint.setObjectName("emptyHint")
        layout.addWidget(self.hint)

        self.query_input.returnPressed.connect(self.open_first_or_current)

    def run_search(self, text):
        self.results.clear()
        query = text.strip()
        if not query:
            self.hint.setText("Type to search. Press Enter or double-click a result to open it.")
            return

        for task_id, title, deadline, completed, project_id, project_name in db.search_tasks(query):
            status = "done" if completed else f"due {deadline}"
            item = QListWidgetItem(f"{title}  -  {project_name}  ({status})")
            item.setData(Qt.ItemDataRole.UserRole, ("task", project_id, task_id))
            if completed:
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
            self.results.addItem(item)

        for date_str, content in db.search_logs(query):
            lowered = content.lower()
            pos = max(0, lowered.find(query.lower()) - 20)
            snippet = content[pos:pos + 70].replace("\n", " ")
            item = QListWidgetItem(f"Log {date_str}:  ...{snippet}...")
            item.setData(Qt.ItemDataRole.UserRole, ("log", date_str))
            self.results.addItem(item)

        count = self.results.count()
        self.hint.setText(f"{count} result{'s' if count != 1 else ''}" if count else "No matches.")
        if count:
            self.results.setCurrentRow(0)

    def open_first_or_current(self):
        if self.results.currentItem():
            self.open_result(self.results.currentItem())

    def open_result(self, item):
        target = item.data(Qt.ItemDataRole.UserRole)
        if not target:
            return
        self.accept()
        self.navigate_callback(target)


class ProjectDateDialog(QDialog):
    def __init__(self, parent=None, start_date=None, end_date=None):
        super().__init__(parent)
        self.setWindowTitle("Project Dates")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        has_dates = bool(start_date or end_date)

        self.use_dates_checkbox = QCheckBox("This project has start and end dates")
        self.use_dates_checkbox.setChecked(has_dates)
        layout.addWidget(self.use_dates_checkbox)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())

        if start_date:
            parsed_start = QDate.fromString(start_date, Qt.DateFormat.ISODate)
            if parsed_start.isValid():
                self.start_date_edit.setDate(parsed_start)
        if end_date:
            parsed_end = QDate.fromString(end_date, Qt.DateFormat.ISODate)
            if parsed_end.isValid():
                self.end_date_edit.setDate(parsed_end)

        self.start_date_edit.setEnabled(has_dates)
        self.end_date_edit.setEnabled(has_dates)

        self.use_dates_checkbox.toggled.connect(self.start_date_edit.setEnabled)
        self.use_dates_checkbox.toggled.connect(self.end_date_edit.setEnabled)

        form.addRow("Start date", self.start_date_edit)
        form.addRow("End date", self.end_date_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ProjectTreeWidget(QTreeWidget):
    def __init__(self, reorder_callback, parent=None):
        super().__init__(parent)
        self.reorder_callback = reorder_callback

    def dropEvent(self, event):
        super().dropEvent(event)
        self.reorder_callback()


class PlannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Personal Work Schedule")
        self.resize(1080, 700)
        db.init_db()

        self.settings = QSettings("PersonalWorkSchedule", "Planner")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        self.project_page_map = {}
        self.project_top_items = []
        self.projects_group_item = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.add_project_btn = QPushButton("+ New Project")
        self.add_project_btn.clicked.connect(self.add_project)
        left_layout.addWidget(self.add_project_btn)

        self.search_btn = QPushButton("Search...  (Ctrl+F)")
        self.search_btn.clicked.connect(self.open_search)
        left_layout.addWidget(self.search_btn)

        self.sidebar = ProjectTreeWidget(self.handle_project_reordered)
        self.sidebar.setHeaderHidden(True)
        self.sidebar.setRootIsDecorated(True)
        self.sidebar.setIndentation(16)
        self.sidebar.setFixedWidth(300)
        self.sidebar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sidebar.setDragEnabled(True)
        self.sidebar.setAcceptDrops(True)
        self.sidebar.setDropIndicatorShown(True)
        self.sidebar.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.sidebar.customContextMenuRequested.connect(self.show_sidebar_context_menu)
        left_layout.addWidget(self.sidebar)

        self.dark_checkbox = QCheckBox("Dark mode")
        self.dark_checkbox.setChecked(self.settings.value("dark", False, type=bool))
        self.dark_checkbox.toggled.connect(self.set_dark_mode)
        left_layout.addWidget(self.dark_checkbox)

        layout.addWidget(left_panel)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.setup_ui()
        self.sidebar.itemClicked.connect(self.navigate)
        self._select_home_item()

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.open_search)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_task_shortcut)
        self.check_reminders()

    def setup_ui(self):
        self.sidebar.clear()
        self.stack = self._reset_stack(self.stack)
        self.project_top_items = []
        self.projects_group_item = None

        self.dashboard_view = DashboardView()
        self.projects_overview_view = ProjectsOverviewView(self.select_project_item)
        self.daily_view = DailyLogView()
        self.calendar_view = CalendarView()

        self.sidebar.addTopLevelItem(self._new_item("Dashboard", "static", 0))
        self.stack.addWidget(self.dashboard_view)

        self.stack.addWidget(self.projects_overview_view)

        self.sidebar.addTopLevelItem(self._new_item("Daily Log", "static", 2))
        self.stack.addWidget(self.daily_view)

        self.sidebar.addTopLevelItem(self._new_item("Calendar", "static", 3))
        self.stack.addWidget(self.calendar_view)

        self.projects_group_item = self._new_item("Projects", "projects_group", 1)
        self.sidebar.addTopLevelItem(self.projects_group_item)

        self.project_page_map = {}
        for project_id, project_name, start_date, end_date in db.get_projects():
            task_rows = db.get_tasks(project_id)
            total_count = len(task_rows)
            open_count = len([row for row in task_rows if not row[6]])
            today = datetime.date.today().isoformat()
            due_today = len([row for row in task_rows if row[3] == today and not row[6]])
            info_suffix = f"  ({open_count}" + (f", {due_today} due" if due_today else "") + ")"

            tree_item = self._new_item(f"{project_name}{info_suffix}", "project", project_id)
            tree_item.setToolTip(0, f"{project_name}\n{open_count}/{total_count} open, {due_today} due today")
            font = tree_item.font(0)
            font.setBold(True)
            tree_item.setFont(0, font)

            self.project_top_items.append(tree_item)
            self.projects_group_item.addChild(tree_item)

            page = TaskView(project_id, self.refresh_all_views)
            self.stack.addWidget(page)
            self.project_page_map[project_id] = page

            tree_item.setExpanded(True)

            self.projects_group_item.setExpanded(True)

    def _new_item(self, text, item_type, payload):
        item = QTreeWidgetItem([text])
        item.setData(0, Qt.ItemDataRole.UserRole, {"type": item_type, "payload": payload})
        if item_type == "header":
            item.setFlags(Qt.NoItemFlags)
        elif item_type == "projects_group":
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsDropEnabled
            )
        elif item_type == "project":
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsDragEnabled
            )
        elif item_type == "task":
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        else:
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        return item

    def _select_home_item(self):
        if self.sidebar.topLevelItemCount() == 0:
            return
        first = self.sidebar.topLevelItem(0)
        if first:
            self.sidebar.setCurrentItem(first)
            self.stack.setCurrentIndex(0)

    def _reset_stack(self, stack):
        while stack.count() > 0:
            widget = stack.widget(0)
            stack.removeWidget(widget)
            widget.deleteLater()
        return stack

    def navigate(self, item, _column):
        if not item:
            return

        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = meta.get("type")
        payload = meta.get("payload")

        if item_type == "header":
            self._select_home_item()
            return

        if item_type == "projects_group":
            if isinstance(payload, int) and 0 <= payload < self.stack.count():
                self.stack.setCurrentIndex(payload)
            return

        if item_type == "static":
            self.stack.setCurrentIndex(payload)
            return

        if item_type in {"project", "task"}:
            projects = list(db.get_projects())
            project_order = [pid for pid, _, _, _ in projects]
            if payload in project_order:
                stack_index = 4 + project_order.index(payload)
                if 0 <= stack_index < self.stack.count():
                    self.stack.setCurrentIndex(stack_index)

    def show_sidebar_context_menu(self, position):
        item = self.sidebar.itemAt(position)
        if item:
            self.sidebar.setCurrentItem(item)

        menu = QMenu(self)

        add_action = menu.addAction("Add Project")
        add_action.triggered.connect(self.add_project)

        project_id = self.get_project_id_from_item(item)
        if project_id is not None:
            rename_action = menu.addAction("Rename Selected Project")
            rename_action.triggered.connect(lambda: self.rename_selected_project(project_id))
            
            branch_action = menu.addAction("Branch Selected Project")
            branch_action.triggered.connect(lambda: self.branch_project(project_id))

            edit_dates_action = menu.addAction("Edit Project Dates")
            edit_dates_action.triggered.connect(lambda: self.edit_project_dates(project_id))

            delete_action = menu.addAction("Delete Selected Project")
            delete_action.triggered.connect(lambda: self.delete_selected_project(project_id))

        menu.addSeparator()
        if item:
            meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
            if meta.get("type") == "projects_group":
                toggle_projects = menu.addAction("Toggle Projects Section")
                toggle_projects.triggered.connect(lambda: item.setExpanded(not item.isExpanded()))
            elif meta.get("type") == "task":
                edit_task_action = menu.addAction("Edit Task Details")
                task_id = meta.get("task_id")
                edit_task_action.triggered.connect(lambda _, tid=task_id: self.open_task_editor(tid))

        expand_action = menu.addAction("Expand All Projects")
        expand_action.triggered.connect(self.sidebar.expandAll)

        collapse_action = menu.addAction("Collapse All Projects")
        collapse_action.triggered.connect(self.sidebar.collapseAll)

        menu.exec(self.sidebar.viewport().mapToGlobal(position))

    def get_project_id_from_item(self, item):
        if not item:
            return None
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = meta.get("type")
        if item_type in {"project", "task"}:
            return meta.get("payload")
        return None

    def handle_project_reordered(self):
        ordered_project_ids = []
        current_item = self.sidebar.currentItem()
        current_project = self.get_project_id_from_item(current_item)

        for idx in range(self.sidebar.topLevelItemCount()):
            top = self.sidebar.topLevelItem(idx)
            top_meta = top.data(0, Qt.ItemDataRole.UserRole) or {}
            if top_meta.get("type") == "project":
                ordered_project_ids.append(top_meta.get("payload"))
            for child_idx in range(top.childCount()):
                child = top.child(child_idx)
                child_meta = child.data(0, Qt.ItemDataRole.UserRole) or {}
                if child_meta.get("type") == "project":
                    ordered_project_ids.append(child_meta.get("payload"))

        if ordered_project_ids:
            db.update_project_order(ordered_project_ids)
            self.setup_ui()
            if current_project is not None:
                self.select_project_item(current_project)
            else:
                self._select_home_item()

    def refresh_all_views(self):
        self.dashboard_view.refresh()
        self.projects_overview_view.refresh()
        self.calendar_view.refresh()
        current_item = self.sidebar.currentItem()
        current_project = None
        if current_item:
            meta = current_item.data(0, Qt.ItemDataRole.UserRole) or {}
            if meta.get("type") in {"project", "task"}:
                current_project = meta.get("payload")

        self.setup_ui()
        if current_project is not None:
            self.select_project_item(current_project)
        else:
            self._select_home_item()

    def select_project_item(self, project_id):
        for index in range(self.sidebar.topLevelItemCount()):
            top = self.sidebar.topLevelItem(index)
            meta = top.data(0, Qt.ItemDataRole.UserRole) or {}
            if meta.get("type") == "project" and meta.get("payload") == project_id:
                self.sidebar.setCurrentItem(top)
                self.navigate(top, 0)
                return
            for child_index in range(top.childCount()):
                child = top.child(child_index)
                child_meta = child.data(0, Qt.ItemDataRole.UserRole) or {}
                if child_meta.get("type") == "project" and child_meta.get("payload") == project_id:
                    top.setExpanded(True)
                    self.sidebar.setCurrentItem(child)
                    self.navigate(child, 0)
                    return

    def add_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return

        start_date = None
        end_date = None
        date_dialog = ProjectDateDialog(self)
        if date_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if date_dialog.use_dates_checkbox.isChecked():
            start_date = date_dialog.start_date_edit.date().toString(Qt.DateFormat.ISODate)
            end_date = date_dialog.end_date_edit.date().toString(Qt.DateFormat.ISODate)
            if date_dialog.end_date_edit.date() < date_dialog.start_date_edit.date():
                QMessageBox.warning(self, "Project Error", "Project end date must be after start date.")
                return

        clean_name = name.strip()
        try:
            db.add_project(clean_name, start_date, end_date)
        except Exception as exc:
            QMessageBox.warning(self, "Project Error", f"Could not add project: {exc}")
            return
            
        self.setup_ui()
        projects = db.get_projects()
        for pid, project_name, _, _ in projects:
            if project_name == clean_name:
                self.select_project_item(pid)
                return
        self._select_home_item()

    def open_task_editor(self, task_id):
        from views import TaskEditDialog
        dlg = TaskEditDialog(task_id, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_all_views()

    def rename_selected_project(self, project_id):
        projects = {pid: name for pid, name, d1, d2 in db.get_projects()}
        current_name = projects.get(project_id, "")
        
        new_name, ok = QInputDialog.getText(self, "Rename Project", "New project name:", QLineEdit.EchoMode.Normal, current_name)
        if ok and new_name.strip():
            db.rename_project(project_id, new_name.strip())
            self.refresh_all_views()

    def edit_project_dates(self, project_id):
        selected_project = None
        for row in db.get_projects():
            if row[0] == project_id:
                selected_project = row
                break

        if selected_project is None:
            QMessageBox.warning(self, "Project Dates", "Project not found.")
            return

        _, _, current_start, current_end = selected_project
        date_dialog = ProjectDateDialog(self, current_start, current_end)
        if date_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_start = None
        new_end = None
        if date_dialog.use_dates_checkbox.isChecked():
            new_start = date_dialog.start_date_edit.date().toString(Qt.DateFormat.ISODate)
            new_end = date_dialog.end_date_edit.date().toString(Qt.DateFormat.ISODate)
            if date_dialog.end_date_edit.date() < date_dialog.start_date_edit.date():
                QMessageBox.warning(self, "Project Dates", "Project end date must be after start date.")
                return

        db.update_project_dates(project_id, new_start, new_end)
        self.refresh_all_views()

    def branch_project(self, source_project_id=None):
        if source_project_id is None:
            source_project_id = self.get_project_id_from_item(self.sidebar.currentItem())
        if source_project_id is None:
            QMessageBox.information(self, "Branch Project", "Select a project to branch.")
            return

        source = None
        for project in db.get_projects():
            if project[0] == source_project_id:
                source = project
                break

        if source is None:
            QMessageBox.warning(self, "Branch Project", "Could not find selected project.")
            return

        _, source_name, start_date, end_date = source
        default_name = f"{source_name} - Branch"
        new_name, ok = QInputDialog.getText(
            self,
            "Branch Project",
            "New branch project name:",
            QLineEdit.EchoMode.Normal,
            default_name,
        )
        if not ok or not new_name.strip():
            return

        clean_name = new_name.strip()
        try:
            db.add_project(clean_name, start_date, end_date)
            projects = db.get_projects()
            target_project_id = None
            for project_id, project_name, _, _ in projects:
                if project_name == clean_name:
                    target_project_id = project_id
                    break

            if target_project_id is None:
                raise ValueError("New branch project was not created.")

            extras = db.get_task_extras(source_project_id)
            for task_id, title, start_date, deadline, start_time, end_time, completed, work_package in db.get_tasks(source_project_id):
                priority, notes = extras.get(task_id, (0, ""))
                db.add_task(target_project_id, title, start_date, deadline, start_time, end_time, completed,
                            work_package or "", priority, notes)
        except Exception as exc:
            QMessageBox.warning(self, "Branch Project", f"Could not branch project: {exc}")
            return

        self.setup_ui()
        self.select_project_item(target_project_id)

    def delete_selected_project(self, project_id=None):
        if project_id is None:
            current = self.sidebar.currentItem()
            project_id = self.get_project_id_from_item(current)
            if current is None:
                QMessageBox.information(self, "Delete Project", "Select a project first.")
                return

        if project_id is None:
            QMessageBox.information(self, "Delete Project", "Select a project or one of its tasks.")
            return

        answer = QMessageBox.question(
            self,
            "Delete Project",
            "Delete this project and all its tasks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        db.delete_project(project_id)
        self.setup_ui()
        self._select_home_item()

    def set_dark_mode(self, dark):
        self.settings.setValue("dark", dark)
        apply_theme(QApplication.instance(), dark)
        self.refresh_all_views()

    def open_search(self):
        dlg = SearchDialog(self.open_search_result, self)
        dlg.exec()

    def select_static_item(self, stack_index):
        for index in range(self.sidebar.topLevelItemCount()):
            top = self.sidebar.topLevelItem(index)
            meta = top.data(0, Qt.ItemDataRole.UserRole) or {}
            if meta.get("type") == "static" and meta.get("payload") == stack_index:
                self.sidebar.setCurrentItem(top)
                self.navigate(top, 0)
                return

    def open_search_result(self, target):
        if target[0] == "log":
            self.select_static_item(2)
            date = QDate.fromString(target[1], Qt.DateFormat.ISODate)
            if date.isValid():
                self.daily_view.date_picker.setDate(date)
            return

        _, project_id, task_id = target
        self.select_project_item(project_id)
        page = self.project_page_map.get(project_id)
        if page is None:
            return
        page.tabs.setCurrentIndex(0)
        page.search.clear()
        page.filter_box.setCurrentIndex(0)
        for row in range(page.task_list.count()):
            item = page.task_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == task_id:
                page.task_list.setCurrentItem(item)
                page.task_list.scrollToItem(item)
                break

    def new_task_shortcut(self):
        page = self.stack.currentWidget()
        if not hasattr(page, "focus_new_task"):
            projects = db.get_projects()
            if not projects:
                return
            self.select_project_item(projects[0][0])
            page = self.project_page_map.get(projects[0][0])
        if page is not None:
            page.focus_new_task()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def check_reminders(self):
        deadlines = db.get_upcoming_deadlines()
        if not deadlines:
            return

        today = datetime.date.today().isoformat()
        due_today = [title for title, date in deadlines if date == today]
        if due_today:
            tasks_str = "\n".join(due_today)
            QMessageBox.information(self, "Daily Reminder", f"Tasks due today:\n{tasks_str}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_theme(app, QSettings("PersonalWorkSchedule", "Planner").value("dark", False, type=bool))

    window = PlannerApp()
    window.show()
    sys.exit(app.exec())

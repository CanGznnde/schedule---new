from PySide6.QtCore import QDate, Qt, QTime, QEvent, QRect, QSize
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QCalendarWidget,
    QDateEdit,
    QCheckBox,
    QTimeEdit,
    QTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QTableView,
    QToolTip,
    QTabWidget,
    QSplitter,
    QTreeWidget,
    QDialog,
    QFormLayout,
    QTreeWidgetItem,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QGraphicsLineItem,
)
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtCore import QEvent

import database as db

CALENDAR_PALETTE = ["#3498db", "#9b59b6", "#1abc9c", "#e67e22", "#34495e", "#2ecc71", "#f1c40f", "#8e44ad", "#d35400", "#c0392b"]
MEETING_COLOR = "#e74c3c"

PRIORITY_LABELS = ["None", "Low", "Medium", "High"]
PRIORITY_COLORS = {2: "#e08a1e", 3: "#d64545"}


def is_dark():
    app = QApplication.instance()
    return bool(app) and app.palette().window().color().lightness() < 128


def gantt_colors():
    if is_dark():
        return {"header": "#2b3138", "grid": "#3a424b", "weekend": "#262b31", "text": "#c5ccd3",
                "title": "#e6eaee", "today": "#ff6b6b", "outside": "#dfe5ea"}
    return {"header": "#f8f9fa", "grid": "#e0e0e0", "weekend": "#f4f6f8", "text": "#666666",
            "title": "#333333", "today": "#e74c3c", "outside": "#333333"}

class TaskCalendarWidget(QCalendarWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_data = {}
        self._cell_rects = {}
        table = self.findChild(QTableView)
        if table:
            table.viewport().installEventFilter(self)

    def paintCell(self, painter, rect, date):
        super().paintCell(painter, rect, date)
        self._cell_rects[rect] = date
        
        if hasattr(self, 'task_data') and date in self.task_data:
            tasks = self.task_data[date]
            if not tasks:
                return

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            radius = 3
            spacing = 3
            diameter = radius * 2
            
            max_circles = 4
            visible_tasks = tasks[:max_circles]
            
            total_width = len(visible_tasks) * diameter + (len(visible_tasks) - 1) * spacing
            start_x = rect.center().x() - (total_width / 2.0)
            y = rect.bottom() - 8
            
            from PySide6.QtCore import Qt
            for i, task in enumerate(visible_tasks):
                color = QColor(task.get("color", "#1f6f8b"))
                
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(color, 2.0))
                
                cx = start_x + (i * (diameter + spacing)) + radius
                cy = y + radius
                
                painter.drawEllipse(int(cx - radius), int(cy - radius), diameter, diameter)
                
            painter.restore()

    def eventFilter(self, obj, event):
        table = self.findChild(QTableView)
        if table and obj == table.viewport() and event.type() == QEvent.Type.ToolTip:
            pos = event.pos()
            for rect, date in self._cell_rects.items():
                if rect.contains(pos):
                    if date in self.task_data and self.task_data[date]:
                        lines = []
                        for t in self.task_data[date]:
                            status = "[Done]" if t.get("completed") else "[Open]"
                            time_str = ""
                            if t.get("start_time") and t.get("end_time"):
                                time_str = f" {t['start_time']}-{t['end_time']}"
                            elif t.get("start_time"):
                                time_str = f" {t['start_time']}"
                            project = f" ({t['project']})" if t.get('project') else ""
                            lines.append(f"{status} {t['title']}{time_str}{project}")
                        QToolTip.showText(event.globalPos(), "\n".join(lines), table.viewport(), rect)
                        return True
                    else:
                        QToolTip.hideText()
                        return True
        return super().eventFilter(obj, event)

    def set_tasks(self, tasks_dict):
        self.task_data = tasks_dict
        self._cell_rects.clear()
        self.updateCells()

class ClickableTextItem(QGraphicsTextItem):
    def __init__(self, text, callback, data=None):
        super().__init__(text)
        self.callback = callback
        self.data = data
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.callback:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.callback(self.data))

class GanttTaskItem(QGraphicsRectItem):
    def __init__(self, task_id, title, start_date, deadline, date_to_x, x_to_date, cb_update, y_pos, color="#1f6f8b", outside_color="#333333"):
        super().__init__()
        self.task_id = task_id
        self.title = title
        self.start_date = start_date
        self.deadline = deadline
        self.date_to_x = date_to_x
        self.x_to_date = x_to_date
        self.cb_update = cb_update
        
        sd = QDate.fromString(start_date, Qt.DateFormat.ISODate)
        ed = QDate.fromString(deadline, Qt.DateFormat.ISODate)
        
        x1 = date_to_x(sd)
        x2 = date_to_x(ed.addDays(1))
        
        self.setRect(0, 0, max(1.0, x2 - x1), 30)
        self.setPos(x1, y_pos)
        
        self.setBrush(QBrush(QColor(color)))
        self.setPen(Qt.PenStyle.NoPen)
        self.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable | QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.text_item = QGraphicsTextItem(title, self)
        self.text_item.setDefaultTextColor(QColor("white"))
        self.text_item.setPos(5, 5)
        if self.text_item.boundingRect().width() + 10 > self.rect().width():
            self.text_item.setDefaultTextColor(QColor(outside_color))
            self.text_item.setPos(self.rect().width() + 4, 5)
        self.setToolTip(f"{title}\n{start_date} to {deadline}")

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        new_x = self.x()
        
        new_start_date = self.x_to_date(new_x)
        duration_days = QDate.fromString(self.start_date, Qt.DateFormat.ISODate).daysTo(QDate.fromString(self.deadline, Qt.DateFormat.ISODate))
        new_endDate = new_start_date.addDays(duration_days)
        
        self.setPos(self.date_to_x(new_start_date), self.y())
        
        self.start_date = new_start_date.toString(Qt.DateFormat.ISODate)
        self.deadline = new_endDate.toString(Qt.DateFormat.ISODate)
        
        self.cb_update(self.task_id, self.start_date, self.deadline)

class GanttTimelineView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.col_width = 80
        self.row_height = 30
        self.view_mode = "months"
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.visible_items = []
        self.all_tasks = []
        self.update_callback = None

    def switch_to_days(self, _):
        self.view_mode = "days"
        self.col_width = 50
        self.populate(self.visible_items, self.all_tasks, self.update_callback, getattr(self, "project_start", None))

    def switch_to_months(self, _):
        self.view_mode = "months"
        self.col_width = 80
        self.populate(self.visible_items, self.all_tasks, self.update_callback, getattr(self, "project_start", None))

    def date_to_x(self, d):
        if self.view_mode == "days":
            return self.min_date.daysTo(d) * self.col_width
        else:
            months = (d.year() - self.min_date.year()) * 12 + d.month() - self.min_date.month()
            fraction = (d.day() - 1) / d.daysInMonth()
            return (months + fraction) * self.col_width

    def x_to_date(self, x):
        if self.view_mode == "days":
            return self.min_date.addDays(round(x / self.col_width))
        else:
            total_months = x / self.col_width
            m = int(total_months)
            fraction = total_months - m
            d = self.min_date.addMonths(m)
            day = int(fraction * d.daysInMonth()) + 1
            day = max(1, min(day, d.daysInMonth()))
            return QDate(d.year(), d.month(), day)

    def populate(self, visible_items, all_tasks, update_callback, project_start=None):
        self.visible_items = visible_items
        self.all_tasks = all_tasks
        self.update_callback = update_callback
        self.project_start = project_start
        self.project_start_date = QDate.fromString(project_start, Qt.DateFormat.ISODate) if project_start else QDate()
        
        self.scene.clear()
        if not all_tasks:
            return

        dates = []
        for t in all_tasks:
            d1 = QDate.fromString(t['start_date'], Qt.DateFormat.ISODate)
            if d1.isValid(): dates.append(d1)
            d2 = QDate.fromString(t['deadline'], Qt.DateFormat.ISODate)
            if d2.isValid(): dates.append(d2)

        if not dates:
            return

        if self.view_mode == "days":
            self.min_date = min(dates).addDays(-2)
            max_d = max(dates).addDays(14)
            num_cols = self.min_date.daysTo(max_d)
        else:
            min_d = min(dates).addMonths(-1)
            self.min_date = QDate(min_d.year(), min_d.month(), 1)
            max_d = max(dates).addMonths(2)
            num_cols = (max_d.year() - self.min_date.year()) * 12 + max_d.month() - self.min_date.month()

        colors = gantt_colors()
        header_h = 60
        h_height = len(visible_items) * self.row_height + header_h

        header_bg = self.scene.addRect(0, 0, (num_cols + 1) * self.col_width, header_h)
        header_bg.setBrush(QBrush(QColor(colors["header"])))
        header_bg.setPen(QPen(QColor(colors["grid"])))
        header_bg.setZValue(1)

        for i in range(num_cols + 1):
            x = i * self.col_width
            
            if self.view_mode == "days":
                d = self.min_date.addDays(i)
                if d.dayOfWeek() in (6, 7):
                    rect = self.scene.addRect(x, header_h, self.col_width, max(0, h_height - header_h))
                    rect.setBrush(QBrush(QColor(colors["weekend"])))
                    rect.setPen(Qt.PenStyle.NoPen)
                else:
                    line = self.scene.addLine(x, 0, x, h_height)
                    line.setPen(QPen(QColor(colors["grid"])))
                
                txt = self.scene.addText(d.toString("dd"))
                txt.setPos(x + 2, header_h - 25)
                txt.setDefaultTextColor(QColor(colors["text"]))
                txt.setZValue(2)

                if d.day() == 1 or i == 0:
                    month_name = d.toString("MMM yyyy")
                    m_indicator = ""
                    if hasattr(self, 'project_start_date') and self.project_start_date.isValid():
                        month_diff = (d.year() - self.project_start_date.year()) * 12 + d.month() - self.project_start_date.month()
                        if month_diff >= 0:
                            m_indicator = f"M{month_diff + 1} - "
                            
                    month_txt = ClickableTextItem(f"{m_indicator}{month_name}", self.switch_to_months)
                    font = month_txt.font()
                    font.setBold(True)
                    month_txt.setFont(font)
                    month_txt.setPos(x + 2, header_h - 45)
                    month_txt.setDefaultTextColor(QColor(colors["title"]))
                    month_txt.setZValue(2)
                    self.scene.addItem(month_txt)
            else:
                d = self.min_date.addMonths(i)
                line = self.scene.addLine(x, 0, x, h_height)
                line.setPen(QPen(QColor(colors["grid"])))
                
                month_name = d.toString("MMM yyyy")
                m_indicator = ""
                if hasattr(self, 'project_start_date') and self.project_start_date.isValid():
                    month_diff = (d.year() - self.project_start_date.year()) * 12 + d.month() - self.project_start_date.month()
                    if month_diff >= 0:
                        m_indicator = f"M{month_diff + 1}\n"
                        
                month_txt = ClickableTextItem(f"{m_indicator}{month_name}", self.switch_to_days, data=d)
                font = month_txt.font()
                font.setBold(True)
                month_txt.setFont(font)
                
                txt_width = month_txt.boundingRect().width()
                month_txt.setPos(x + (self.col_width - txt_width) / 2, (header_h - month_txt.boundingRect().height()) / 2)
                month_txt.setDefaultTextColor(QColor(colors["title"]))
                month_txt.setZValue(2)
                self.scene.addItem(month_txt)

        y = header_h
        for t in visible_items:
            if t["type"] == "package":
                sd = QDate.fromString(t['start_date'], Qt.DateFormat.ISODate)
                ed = QDate.fromString(t['deadline'], Qt.DateFormat.ISODate)
                if sd.isValid() and ed.isValid():
                    x1 = self.date_to_x(sd)
                    x2 = self.date_to_x(ed.addDays(1))
                    rect = self.scene.addRect(x1, y + 4, max(1.0, x2 - x1), self.row_height - 8)
                    rect.setBrush(QBrush(QColor(t.get("color", "#3a3a3a"))))
                    rect.setPen(Qt.PenStyle.NoPen)
                    
                    lbl = self.scene.addText(t['title'])
                    lbl.setZValue(10)
                    if lbl.boundingRect().width() + 10 > x2 - x1:
                        lbl.setDefaultTextColor(QColor(colors["outside"]))
                        lbl.setPos(x2 + 4, y + 5)
                    else:
                        lbl.setDefaultTextColor(QColor("white"))
                        lbl.setPos(x1 + 5, y + 5)
            else:
                base_color = QColor(t.get("color", "#1f6f8b"))
                if t.get("has_subtasks", False):
                    base_color = base_color.lighter(140)
                    
                item = GanttTaskItem(t['id'], t['title'], t['start_date'], t['deadline'], self.date_to_x, self.x_to_date, update_callback, y, base_color.name(), colors["outside"])
                item.setRect(0, 4, item.rect().width(), self.row_height - 8)
                item.setZValue(10)
                self.scene.addItem(item)
            y += self.row_height
            
        today = QDate.currentDate()
        today_x = self.date_to_x(today)
        if 0 <= today_x <= (num_cols + 1) * self.col_width:
            if self.view_mode == "days":
                today_x += self.col_width / 2
            today_line = self.scene.addLine(today_x, 0, today_x, y)
            today_line.setPen(QPen(QColor(colors["today"]), 2, Qt.PenStyle.DashLine))
            today_line.setZValue(5)
            today_line.setToolTip("Today")
            today_lbl = self.scene.addText("Today")
            today_lbl.setDefaultTextColor(QColor(colors["today"]))
            today_lbl.setPos(today_x + 2, header_h - 22)
            today_lbl.setZValue(6)

        self.setSceneRect(0, 0, (num_cols + 1) * self.col_width, y + 20)


class GanttTab(QWidget):
    def __init__(self, update_callback):
        super().__init__()
        self.update_callback = update_callback
        
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Work Package / Task", "Days", "Start", "Deadline"])
        self.tree.setIndentation(0)
        self.tree.setColumnWidth(0, 170)
        self.tree.setColumnWidth(1, 55)
        self.tree.setColumnWidth(2, 90)
        self.tree.setColumnWidth(3, 90)
        
        self.timeline = GanttTimelineView()
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.timeline)
        splitter.setSizes([430, 600])
        root.addWidget(splitter)
        
        self.tree.verticalScrollBar().valueChanged.connect(self.timeline.verticalScrollBar().setValue)
        self.timeline.verticalScrollBar().valueChanged.connect(self.tree.verticalScrollBar().setValue)
        
        self.tree.itemExpanded.connect(self.redraw_timeline)
        self.tree.itemCollapsed.connect(self.redraw_timeline)
        self.tree.itemDoubleClicked.connect(self.open_task_details)
        
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.setIndentation(12)

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") != "task": return
        
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        edit_action = menu.addAction("Edit Task Details")
        edit_action.triggered.connect(lambda: self.edit_task(data["id"]))
        menu.exec(self.tree.viewport().mapToGlobal(pos))
        
    def edit_task(self, task_id):
        dlg = TaskEditDialog(task_id, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.update_callback()

    def open_task_details(self, item, column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") != "task":
            return
        dlg = TaskDetailsDialog(data["id"], data["title"], self)
        dlg.exec()
        self.update_callback()

    def load_tasks(self, tasks, project_start=None):
        self.tree.clear()
        self.raw_tasks = tasks
        self.project_start = project_start
        from collections import defaultdict
        grouped = defaultdict(list)
        for t in tasks:
            grouped[t["work_package"]].append(t)

        for idx, (wp, group_tasks) in enumerate(grouped.items()):
            theme_color = CALENDAR_PALETTE[idx % len(CALENDAR_PALETTE)]
            if wp.lower() == "meeting":
                theme_color = MEETING_COLOR

            d_starts = [QDate.fromString(t['start_date'], Qt.DateFormat.ISODate) for t in group_tasks if QDate.fromString(t['start_date'], Qt.DateFormat.ISODate).isValid()]
            d_ends = [QDate.fromString(t['deadline'], Qt.DateFormat.ISODate) for t in group_tasks if QDate.fromString(t['deadline'], Qt.DateFormat.ISODate).isValid()]
            
            p_start = min(d_starts).toString(Qt.DateFormat.ISODate) if d_starts else ""
            p_end = max(d_ends).toString(Qt.DateFormat.ISODate) if d_ends else ""
            
            p_duration = f"{min(d_starts).daysTo(max(d_ends)) + 1}d" if d_starts and d_ends else ""
            
            pkg_item = QTreeWidgetItem([wp, p_duration, p_start, p_end])
            font = pkg_item.font(0)
            font.setBold(True)
            for i in range(4):
                pkg_item.setFont(i, font)
                
            pkg_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "package", "title": wp, "start_date": p_start, "deadline": p_end, "color": theme_color})
            pkg_item.setSizeHint(0, QSize(0, self.timeline.row_height))
            
            for t in group_tasks:
                sd = QDate.fromString(t['start_date'], Qt.DateFormat.ISODate)
                ed = QDate.fromString(t['deadline'], Qt.DateFormat.ISODate)
                duration = f"{sd.daysTo(ed) + 1}d" if sd.isValid() and ed.isValid() else ""
                
                display_title = t['title'] + (" (☑)" if t.get("has_subtasks") else "")
                t_item = QTreeWidgetItem([display_title, duration, t['start_date'], t['deadline']])
                t_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "task", "color": theme_color, **t})
                t_item.setSizeHint(0, QSize(0, self.timeline.row_height))
                pkg_item.addChild(t_item)
                
            self.tree.addTopLevelItem(pkg_item)
            pkg_item.setExpanded(True)
            
        self.redraw_timeline()

    def redraw_timeline(self):
        visible_items = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            visible_items.append(top.data(0, Qt.ItemDataRole.UserRole))
            if top.isExpanded():
                for j in range(top.childCount()):
                    child = top.child(j)
                    visible_items.append(child.data(0, Qt.ItemDataRole.UserRole))
        
        self.timeline.populate(visible_items, getattr(self, "raw_tasks", []), self.handle_task_moved, getattr(self, "project_start", None))

    def handle_task_moved(self, task_id, start_date, deadline):
        import database as db
        db.update_task_dates(task_id, start_date, deadline)
        self.update_callback()

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

        self.delete_btn = QPushButton("Delete Selected / Checked")
        self.delete_btn.clicked.connect(self.delete_selected_task)
        self.delete_btn.setEnabled(False)
        self.task_list.currentItemChanged.connect(self.on_current_item_changed)

        action_row.addWidget(self.finish_btn)
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

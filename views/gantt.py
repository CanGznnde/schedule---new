from PySide6.QtCore import QDate, Qt, QSize
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QSplitter,
    QTreeWidget,
    QDialog,
    QTreeWidgetItem,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsTextItem,
)

from .theme import CALENDAR_PALETTE, MEETING_COLOR, gantt_colors
from .dialogs import TaskDetailsDialog, TaskEditDialog


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

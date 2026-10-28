from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QCalendarWidget, QTableView, QToolTip


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

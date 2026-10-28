"""UI views for the planner, one module per screen."""

from .archive import ArchiveView
from .calendar_view import CalendarView
from .calendar_widget import TaskCalendarWidget
from .daily_log import DailyLogView
from .dashboard import DashboardView, ProjectsOverviewView, StatCard
from .dialogs import TaskDetailsDialog, TaskEditDialog
from .gantt import GanttTab
from .tasks import TaskView

__all__ = [
    "ArchiveView",
    "CalendarView",
    "DailyLogView",
    "DashboardView",
    "GanttTab",
    "ProjectsOverviewView",
    "StatCard",
    "TaskCalendarWidget",
    "TaskDetailsDialog",
    "TaskEditDialog",
    "TaskView",
]

from PySide6.QtWidgets import QApplication

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

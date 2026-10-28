import os
import sys
import tempfile
from pathlib import Path

# Never touch a real planner.db: point the app at a throwaway file before anything imports it,
# and render Qt offscreen so the GUI tests run headless.
os.environ["PLANNER_DB"] = str(Path(tempfile.mkdtemp(prefix="planner-tests-")) / "import-time.db")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import database  # noqa: E402


@pytest.fixture
def db(tmp_path, monkeypatch):
    """The database module pointed at a fresh, initialised database in tmp_path."""
    monkeypatch.setattr(database, "DB_NAME", str(tmp_path / "test.db"))
    database.init_db()
    return database


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    # Keep QSettings (theme, window geometry) out of the real user settings.
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("settings")))
    return QApplication.instance() or QApplication([])


@pytest.fixture
def quiet_dialogs(monkeypatch):
    """Answer message boxes automatically: questions with Yes, everything else dismissed."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))

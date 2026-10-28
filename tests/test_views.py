import pytest
from PySide6.QtCore import QMimeData, QUrl, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QListWidgetItem

import main
from views import ArchiveView, DailyLogView, TaskEditDialog, TaskView
from views.daily_log import MAX_IMAGE_WIDTH
from views.theme import is_dark


@pytest.fixture
def window(qapp, db, quiet_dialogs):
    win = main.PlannerApp()
    yield win
    win.close()


def make_image(path, width=800, height=600):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#3498db"))
    assert image.save(str(path))
    return path


def project_id(db, name):
    return next(pid for pid, pname, *_ in db.get_projects() if pname == name)


def task_titles(page):
    return [page.task_list.item(i).text() for i in range(page.task_list.count())]


# --- task view -------------------------------------------------------------

def test_add_task_with_priority_and_filter(qapp, db):
    pid = project_id(db, "General")
    page = TaskView(pid, lambda: None)

    page.task_input.setText("Urgent")
    page.priority_input.setCurrentIndex(3)
    page.add_task()
    page.task_input.setText("Calm")
    page.add_task()

    assert any(t.startswith("[High] Urgent") for t in task_titles(page))
    page.filter_box.setCurrentText("High Priority")
    assert len(task_titles(page)) == 1


def test_empty_list_shows_hint(qapp, db):
    page = TaskView(project_id(db, "General"), lambda: None)
    assert task_titles(page) == ["No tasks yet. Type a title above and press Enter."]


def test_tab_label_shows_ampersand(qapp, db):
    page = TaskView(project_id(db, "General"), lambda: None)
    assert page.tabs.tabText(0) == "List && Calendar"  # '&&' renders as a literal '&'


def test_edit_dialog_saves_priority_and_notes(qapp, db):
    pid = project_id(db, "General")
    db.add_task(pid, "T", "2026-01-01", "2026-01-02")
    tid = db.get_tasks(pid)[0][0]

    dialog = TaskEditDialog(tid)
    dialog.priority_input.setCurrentIndex(2)
    dialog.notes_input.setPlainText("details")
    dialog.save_task()

    assert db.get_task(tid)[9:] == (2, "details")


def test_archive_completed_and_restore_from_archive_view(qapp, db, quiet_dialogs):
    pid = project_id(db, "General")
    db.add_task(pid, "done", "2026-01-01", "2026-01-02", completed=1)
    db.add_task(pid, "open", "2026-01-01", "2026-01-02")
    page = TaskView(pid, lambda: None)

    page.archive_completed()
    assert [t for t in task_titles(page) if "done" in t] == []

    view = ArchiveView(lambda: None)
    assert "done" in view.task_list.item(0).text()
    view.task_list.setCurrentRow(0)
    view.restore_task()
    assert db.get_archived_tasks() == [] and len(db.get_tasks(pid)) == 2


def test_archive_view_deletes_project_permanently(qapp, db, quiet_dialogs):
    db.add_project("Gone")
    pid = project_id(db, "Gone")
    db.set_project_archived(pid)

    view = ArchiveView(lambda: None)
    view.project_list.setCurrentRow(0)
    view.delete_project()

    assert db.get_archived_projects() == [] and db.get_project(pid) is None


def test_archive_view_placeholders_when_empty(qapp, db):
    view = ArchiveView(lambda: None)
    for widget in (view.project_list, view.task_list):
        item: QListWidgetItem = widget.item(0)
        assert item.text().startswith("No archived") and not item.flags() & Qt.ItemFlag.ItemIsSelectable


# --- daily log images ------------------------------------------------------

def test_log_image_from_file_is_stored_scaled_and_survives_reload(qapp, db, tmp_path):
    source = make_image(tmp_path / "shot.png", 800, 600)
    view = DailyLogView()

    assert view.text_area.insert_image_file(source)

    saved = db.get_log(view.date_picker.date().toString(Qt.DateFormat.ISODate))
    assert db.is_rich_log(saved) and "attachments/" in saved
    attachment = next(db.attachments_dir().iterdir())
    assert attachment.read_bytes() == source.read_bytes()

    reloaded = DailyLogView()
    reloaded.text_area.document().setTextWidth(900)
    # 800x600 is scaled down to MAX_IMAGE_WIDTH wide, i.e. 480 tall; a text-only log would be ~20px.
    assert reloaded.text_area.document().size().height() >= MAX_IMAGE_WIDTH * 600 / 800
    assert "[image]" in db.log_to_plain(saved)


def test_pasting_an_image_stores_a_png(qapp, db, tmp_path):
    view = DailyLogView()
    mime = QMimeData()
    mime.setImageData(QImage(100, 50, QImage.Format.Format_RGB32))

    assert view.text_area.canInsertFromMimeData(mime)
    view.text_area.insertFromMimeData(mime)

    files = list(db.attachments_dir().iterdir())
    assert len(files) == 1 and files[0].suffix == ".png"
    assert "<img" in view.text_area.log_content()


def test_dropping_image_files_inserts_them_and_ignores_other_files(qapp, db, tmp_path):
    image = make_image(tmp_path / "pic.jpg", 100, 100)
    other = tmp_path / "notes.txt"
    other.write_text("x")
    view = DailyLogView()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(image)), QUrl.fromLocalFile(str(other))])

    view.text_area.insertFromMimeData(mime)

    assert len(list(db.attachments_dir().iterdir())) == 1
    assert view.text_area.toPlainText().count("￼") == 1  # one embedded image, no stray text


def test_text_only_log_stays_plain_text(qapp, db):
    view = DailyLogView()
    view.text_area.setPlainText("just words")
    view.auto_save()
    saved = db.get_log(view.date_picker.date().toString(Qt.DateFormat.ISODate))
    assert saved == "just words" and not db.is_rich_log(saved)


def test_pasted_rich_text_becomes_plain(qapp, db):
    view = DailyLogView()
    mime = QMimeData()
    mime.setHtml("<p style='color:red'>styled</p>")
    mime.setText("styled")
    view.text_area.insertFromMimeData(mime)
    assert "color" not in view.text_area.log_content() and view.text_area.toPlainText() == "styled"


def test_unreadable_image_is_rejected(qapp, db, tmp_path):
    bogus = tmp_path / "bad.png"
    bogus.write_text("not an image")
    assert DailyLogView().text_area.insert_image_file(bogus) is False
    assert not db.attachments_dir().exists()


# --- main window -----------------------------------------------------------

def test_sidebar_has_archive_and_compact_project_labels(window, db):
    labels = [window.sidebar.topLevelItem(i).text(0) for i in range(window.sidebar.topLevelItemCount())]
    assert "Archive" in labels
    child = window.projects_group_item.child(0)
    assert child.text(0).startswith("General") and "[" not in child.text(0)


def test_navigation_reaches_the_right_pages(window, db):
    db.add_project("Second")
    window.setup_ui()
    pid = project_id(db, "Second")

    window.select_project_item(pid)
    assert window.stack.currentWidget() is window.project_page_map[pid]

    window.select_static_item(4)
    assert window.stack.currentWidget() is window.archive_view


def test_archiving_a_project_removes_it_from_the_sidebar(window, db):
    db.add_project("Temp")
    window.setup_ui()
    pid = project_id(db, "Temp")

    window.archive_project(pid)

    names = [window.projects_group_item.child(i).text(0) for i in range(window.projects_group_item.childCount())]
    assert not any(n.startswith("Temp") for n in names)
    assert pid not in window.project_page_map and db.get_archived_projects()[0][1] == "Temp"


def test_refresh_keeps_current_static_page(window, db):
    window.select_static_item(4)
    window.refresh_all_views()
    assert window.stack.currentWidget() is window.archive_view


def test_search_dialog_finds_tasks_and_logs_but_not_archived(window, db):
    pid = project_id(db, "General")
    db.add_task(pid, "Kick-off visible", "2026-01-01", "2026-01-02")
    db.add_task(pid, "Kick-off hidden", "2026-01-01", "2026-01-02")
    hidden = next(row[0] for row in db.get_tasks(pid) if row[1] == "Kick-off hidden")
    db.set_task_archived(hidden)
    db.save_log("2026-01-01", "the kick-off went well")

    dialog = main.SearchDialog(lambda target: None, window)
    dialog.query_input.setText("kick-off")

    targets = [dialog.results.item(i).data(Qt.ItemDataRole.UserRole) for i in range(dialog.results.count())]
    assert sorted(t[0] for t in targets) == ["log", "task"]
    task_text = next(dialog.results.item(i).text() for i, t in enumerate(targets) if t[0] == "task")
    assert "visible" in task_text


def test_dark_mode_toggle_persists_and_rebuilds(window, db):
    window.dark_checkbox.setChecked(True)
    assert is_dark()
    window.dark_checkbox.setChecked(False)
    assert not is_dark()

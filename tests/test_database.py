import datetime
import sqlite3

import database


def today(offset=0):
    return (datetime.date.today() + datetime.timedelta(days=offset)).isoformat()


def new_project(db, name="Alpha"):
    db.add_project(name)
    return next(pid for pid, pname, *_ in db.get_projects() if pname == name)


def new_task(db, project_id, title="Task", start=0, end=0, **kwargs):
    db.add_task(project_id, title, today(start), today(end), **kwargs)
    return max(row[0] for row in db.get_tasks(project_id) if row[1] == title)


# --- setup and migration ---------------------------------------------------

def test_init_creates_default_project(db):
    assert [name for _, name, *_ in db.get_projects()] == ["General"]


def test_db_path_override(monkeypatch, tmp_path):
    target = tmp_path / "custom.db"
    monkeypatch.setenv("PLANNER_DB", str(target))
    assert database.get_db_path() == str(target.resolve())


def test_old_database_is_migrated_in_place(db, tmp_path, monkeypatch):
    old = tmp_path / "old.db"
    with sqlite3.connect(old) as conn:
        conn.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, project_id INTEGER, title TEXT, deadline TEXT, completed INTEGER DEFAULT 0)")
        conn.execute("INSERT INTO projects (name) VALUES ('Legacy')")
        conn.execute("INSERT INTO tasks (project_id, title, deadline) VALUES (1, 'Old task', '2026-01-02')")
    monkeypatch.setattr(database, "DB_NAME", str(old))

    database.init_db()

    columns = {row[1] for row in sqlite3.connect(old).execute("PRAGMA table_info(tasks)")}
    assert {"start_date", "work_package", "priority", "notes", "archived"} <= columns
    task = database.get_tasks(1)[0]
    assert task[1] == "Old task" and task[2] == "2026-01-02"  # start_date backfilled from deadline


# --- projects --------------------------------------------------------------

def test_project_order_and_rename(db):
    a, b = new_project(db, "A"), new_project(db, "B")
    general = db.get_projects()[0][0]
    db.update_project_order([b, a, general])  # the sidebar always sends every project
    assert [pid for pid, *_ in db.get_projects()] == [b, a, general]
    db.rename_project(a, "A2")
    assert db.get_project(a)[1] == "A2"


def test_delete_last_project_recreates_general(db):
    for pid, *_ in db.get_projects():
        db.delete_project(pid)
    assert [name for _, name, *_ in db.get_projects()] == ["General"]


# --- tasks -----------------------------------------------------------------

def test_task_priority_notes_roundtrip(db):
    pid = new_project(db)
    tid = new_task(db, pid, priority=3, notes="remember")
    assert db.get_task(tid)[9:] == (3, "remember")
    db.update_task_details(tid, "Renamed", today(), today(1), None, None, "WP", 1, "changed")
    task = db.get_task(tid)
    assert task[2] == "Renamed" and task[8] == "WP" and task[9:] == (1, "changed")
    assert db.get_task_extras(pid) == {tid: (1, "changed")}


def test_toggle_and_delete_task_removes_subtasks(db):
    pid = new_project(db)
    tid = new_task(db, pid)
    db.toggle_task_completion(tid, 1)
    assert db.get_task(tid)[7] == 1
    db.add_subtask(tid, "step")
    assert db.get_subtask_counts(pid) == {tid: 1}
    db.delete_task(tid)
    assert db.get_task(tid) is None and db.get_subtasks(tid) == []


def test_subtasks(db):
    pid = new_project(db)
    tid = new_task(db, pid)
    db.add_subtask(tid, "one")
    sid = db.get_subtasks(tid)[0][0]
    db.toggle_subtask(sid, 1)
    assert db.get_subtasks(tid)[0][2] == 1
    db.delete_subtask(sid)
    assert db.get_subtasks(tid) == []


def test_dashboard_stats_deadlines_and_meeting(db):
    pid = new_project(db)
    new_task(db, pid, "due today", 0, 0)
    new_task(db, pid, "overdue", -5, -2)
    done = new_task(db, pid, "done", -1, -1)
    db.toggle_task_completion(done, 1)
    new_task(db, pid, "standup", 1, 1, work_package="Meeting")

    stats = db.get_dashboard_stats()
    assert stats["total_tasks"] == 4 and stats["completed_tasks"] == 1 and stats["open_tasks"] == 3
    assert stats["due_today"] == 1 and stats["overdue"] == 1
    assert [t for t, _ in db.get_upcoming_deadlines()] == ["due today", "standup"]
    assert db.get_upcoming_meeting()[0] == "standup"


def test_tasks_for_date_covers_ranges(db):
    pid = new_project(db)
    new_task(db, pid, "range", -2, 2)
    new_task(db, pid, "later", 5, 6)
    assert [row[0] for row in db.get_tasks_for_date(today())] == ["range"]
    assert [row[1] for row in db.get_tasks_for_project_date(pid, today())] == ["range"]


# --- search ----------------------------------------------------------------

def test_search_matches_fields_and_escapes_wildcards(db):
    pid = new_project(db, "Website")
    new_task(db, pid, "Write 100% report", notes="needs_data")
    new_task(db, pid, "Plain", work_package="Docs")
    assert [r[1] for r in db.search_tasks("100%")] == ["Write 100% report"]
    assert len(db.search_tasks("needs_")) == 1  # '_' is literal, not a wildcard
    assert len(db.search_tasks("docs")) == 1     # work package, case-insensitive
    assert len(db.search_tasks("website")) == 2  # project name
    assert db.search_tasks("zzz") == []


# --- archive ---------------------------------------------------------------

def test_archived_task_is_hidden_everywhere_and_restorable(db):
    pid = new_project(db)
    tid = new_task(db, pid, "Hidden", 0, 0, work_package="Meeting", notes="findme")
    new_task(db, pid, "Visible", 0, 0)

    db.set_task_archived(tid)

    assert [r[1] for r in db.get_tasks(pid)] == ["Visible"]
    assert db.get_dashboard_stats()["total_tasks"] == 1
    assert [t for t, _ in db.get_upcoming_deadlines()] == ["Visible"]
    assert db.get_upcoming_meeting() is None
    assert [r[0] for r in db.get_tasks_for_date(today())] == ["Visible"]
    assert [r[1] for r in db.get_tasks_for_project_date(pid, today())] == ["Visible"]
    assert [r[0] for r in db.get_all_tasks()] == ["Visible"]
    assert db.search_tasks("findme") == []
    assert [r[1] for r in db.get_archived_tasks()] == ["Hidden"]

    db.set_task_archived(tid, False)
    assert len(db.get_tasks(pid)) == 2 and db.get_archived_tasks() == []


def test_archive_completed_only_touches_completed_tasks(db):
    pid = new_project(db)
    done1, done2 = new_task(db, pid, "d1"), new_task(db, pid, "d2")
    new_task(db, pid, "open")
    for tid in (done1, done2):
        db.toggle_task_completion(tid, 1)

    assert db.archive_completed_tasks(pid) == 2
    assert db.archive_completed_tasks(pid) == 0
    assert [r[1] for r in db.get_tasks(pid)] == ["open"]


def test_archived_project_is_hidden_and_restorable(db):
    pid = new_project(db, "Old")
    new_task(db, pid, "inside", 0, 0, work_package="Meeting")

    db.set_project_archived(pid)

    assert "Old" not in [name for _, name, *_ in db.get_projects()]
    stats = db.get_dashboard_stats()
    assert stats["total_tasks"] == 0 and stats["projects"] == 1
    assert db.get_all_tasks() == [] and db.get_upcoming_deadlines() == [] and db.get_upcoming_meeting() is None
    assert db.search_tasks("inside") == []
    assert db.get_archived_projects()[0][1:] == ("Old", None, None, 1)

    db.set_project_archived(pid, False)
    assert "Old" in [name for _, name, *_ in db.get_projects()]
    assert db.get_dashboard_stats()["total_tasks"] == 1


# --- daily logs and attachments --------------------------------------------

def test_plain_log_roundtrip_and_search(db):
    db.save_log("2026-03-01", "Met the client about Budget")
    assert db.get_log("2026-03-01") == "Met the client about Budget"
    assert db.get_log("2026-03-02") == ""
    assert db.search_logs("budget") == [("2026-03-01", "Met the client about Budget")]


def test_html_log_is_searched_by_its_text(db):
    html = (
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN"><html><head><style>p {color:red}</style></head>'
        '<body><p>Sketch of the <b>plan</b> &amp; notes</p><p><img src="attachments/a.png" width="10" /></p></body></html>'
    )
    db.save_log("2026-03-01", html)
    plain = db.log_to_plain(html)
    assert "Sketch of the plan & notes" in plain and "[image]" in plain and "color" not in plain
    assert db.search_logs("plan &")[0][0] == "2026-03-01"
    assert db.search_logs("attachments") == []  # markup is not searchable


def test_attachments_are_stored_next_to_the_database(db, tmp_path):
    relative = db.store_attachment(b"data", ".PNG")
    assert relative.startswith("attachments/") and relative.endswith(".png")
    assert db.attachment_path(relative).read_bytes() == b"data"
    assert db.attachment_path(relative).parent == tmp_path / "attachments"
    assert db.store_attachment(b"x", "bad").endswith(".png")  # unusable suffix falls back to .png

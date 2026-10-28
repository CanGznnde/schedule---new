import html
import os
import re
import sys
import sqlite3
import uuid
import datetime
from pathlib import Path

def get_db_path():
    """Return the database file: $PLANNER_DB if set, else planner.db next to the app."""
    override = os.environ.get("PLANNER_DB")
    if override:
        return str(Path(override).expanduser().resolve())

    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent
    return str(base_dir / "planner.db")

DB_NAME = get_db_path()

# SQL condition for tasks (alias t) in projects (alias p) that are not archived.
_ACTIVE = "ifnull(t.archived, 0) = 0 AND ifnull(p.archived, 0) = 0"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # Projects Table
        c.execute(
            '''CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                start_date TEXT,
                end_date TEXT,
                sort_order INTEGER
            )'''
        )
        # Tasks Table
        c.execute(
            '''CREATE TABLE IF NOT EXISTS tasks 
                     (id INTEGER PRIMARY KEY, project_id INTEGER, title TEXT, 
                      start_date TEXT, deadline TEXT, start_time TEXT, end_time TEXT, completed INTEGER DEFAULT 0, work_package TEXT DEFAULT '')'''
        )
        # Subtasks Table
        c.execute('''CREATE TABLE IF NOT EXISTS subtasks 
                     (id INTEGER PRIMARY KEY, task_id INTEGER, title TEXT, completed INTEGER DEFAULT 0)''')
        # Daily Logs Table
        c.execute('''CREATE TABLE IF NOT EXISTS daily_logs 
                     (date TEXT PRIMARY KEY, content TEXT)''')

        # Lightweight migrations for existing databases.
        project_columns = [row[1] for row in c.execute("PRAGMA table_info(projects)").fetchall()]
        if "start_date" not in project_columns:
            c.execute("ALTER TABLE projects ADD COLUMN start_date TEXT")
        if "end_date" not in project_columns:
            c.execute("ALTER TABLE projects ADD COLUMN end_date TEXT")
        if "sort_order" not in project_columns:
            c.execute("ALTER TABLE projects ADD COLUMN sort_order INTEGER")

        project_rows = c.execute("SELECT id, sort_order FROM projects ORDER BY id").fetchall()
        for idx, (project_id, sort_order) in enumerate(project_rows):
            if sort_order is None:
                c.execute("UPDATE projects SET sort_order = ? WHERE id = ?", (idx, project_id))

        task_columns = [row[1] for row in c.execute("PRAGMA table_info(tasks)").fetchall()]
        if "start_date" not in task_columns:
            c.execute("ALTER TABLE tasks ADD COLUMN start_date TEXT")
            c.execute("UPDATE tasks SET start_date = deadline WHERE start_date IS NULL")
        if "start_time" not in task_columns:
            c.execute("ALTER TABLE tasks ADD COLUMN start_time TEXT")
        if "end_time" not in task_columns:
            c.execute("ALTER TABLE tasks ADD COLUMN end_time TEXT")
        if "work_package" not in task_columns:
            c.execute("ALTER TABLE tasks ADD COLUMN work_package TEXT DEFAULT ''")
        if "priority" not in task_columns:
            c.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0")
        if "notes" not in task_columns:
            c.execute("ALTER TABLE tasks ADD COLUMN notes TEXT DEFAULT ''")
        if "archived" not in task_columns:
            c.execute("ALTER TABLE tasks ADD COLUMN archived INTEGER DEFAULT 0")
        if "archived" not in project_columns:
            c.execute("ALTER TABLE projects ADD COLUMN archived INTEGER DEFAULT 0")
        
        # Insert a default project if empty
        c.execute("SELECT COUNT(*) FROM projects")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO projects (name) VALUES ('General')")
        conn.commit()

def get_projects():
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            "SELECT id, name, start_date, end_date FROM projects WHERE ifnull(archived, 0) = 0 ORDER BY sort_order ASC, id ASC"
        ).fetchall()

def get_project(project_id):
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            "SELECT id, name, start_date, end_date FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()

def add_project(name, start_date=None, end_date=None):
    with sqlite3.connect(DB_NAME) as conn:
        max_order_row = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM projects").fetchone()
        next_order = max_order_row[0] + 1
        conn.execute(
            "INSERT INTO projects (name, start_date, end_date, sort_order) VALUES (?, ?, ?, ?)",
            (name, start_date, end_date, next_order),
        )

def update_project_dates(project_id, start_date=None, end_date=None):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "UPDATE projects SET start_date = ?, end_date = ? WHERE id = ?",
            (start_date, end_date, project_id),
        )

def update_project_order(project_ids):
    with sqlite3.connect(DB_NAME) as conn:
        for index, project_id in enumerate(project_ids):
            conn.execute("UPDATE projects SET sort_order = ? WHERE id = ?", (index, project_id))

def delete_project(project_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

        remaining = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        if remaining == 0:
            conn.execute("INSERT INTO projects (name) VALUES ('General')")

def rename_project(project_id, new_name):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE projects SET name=? WHERE id=?", (new_name, project_id))

def get_task(task_id):
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            """
            SELECT id, project_id, title, start_date, deadline, start_time, end_time, completed, work_package,
                   ifnull(priority, 0), ifnull(notes, '')
            FROM tasks
            WHERE id=?
            """,
            (task_id,),
        ).fetchone()

def update_task_details(task_id, title, start_date, deadline, start_time, end_time, work_package, priority=0, notes=""):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            """
            UPDATE tasks
            SET title=?, start_date=?, deadline=?, start_time=?, end_time=?, work_package=?, priority=?, notes=?
            WHERE id=?
            """,
            (title, start_date, deadline, start_time, end_time, work_package, priority, notes, task_id)
        )

def get_tasks(project_id):
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            """
            SELECT id, title, start_date, deadline, start_time, end_time, completed, work_package
            FROM tasks
            WHERE project_id=? AND ifnull(archived, 0) = 0
            ORDER BY completed ASC, deadline ASC, id DESC
            """,
            (project_id,),
        ).fetchall()

def add_task(project_id, title, start_date, deadline, start_time=None, end_time=None, completed=0, work_package="", priority=0, notes=""):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT INTO tasks (project_id, title, start_date, deadline, start_time, end_time, completed, work_package, priority, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, title, start_date, deadline, start_time, end_time, completed, work_package, priority, notes),
        )

def get_task_extras(project_id):
    """Return {task_id: (priority, notes)} for a project's tasks."""
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute(
            "SELECT id, ifnull(priority, 0), ifnull(notes, '') FROM tasks WHERE project_id=?",
            (project_id,),
        ).fetchall()
    return {row[0]: (row[1], row[2]) for row in rows}

def update_task_dates(task_id, start_date, deadline):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "UPDATE tasks SET start_date=?, deadline=? WHERE id=?",
            (start_date, deadline, task_id),
        )

def toggle_task_completion(task_id, completed):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE tasks SET completed=? WHERE id=?", (completed, task_id))

def delete_task(task_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.execute("DELETE FROM subtasks WHERE task_id=?", (task_id,))

def get_subtasks(task_id):
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("SELECT id, title, completed FROM subtasks WHERE task_id=? ORDER BY completed ASC, id ASC", (task_id,)).fetchall()

def add_subtask(task_id, title):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO subtasks (task_id, title) VALUES (?, ?)", (task_id, title))

def toggle_subtask(subtask_id, completed):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE subtasks SET completed=? WHERE id=?", (completed, subtask_id))

def delete_subtask(subtask_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM subtasks WHERE id=?", (subtask_id,))

def get_subtask_counts(project_id):
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute("""
            SELECT t.id, COUNT(s.id) 
            FROM tasks t 
            LEFT JOIN subtasks s ON s.task_id = t.id 
            WHERE t.project_id = ? 
            GROUP BY t.id
        """, (project_id,)).fetchall()
        return {r[0]: r[1] for r in rows}

def get_log(date_str):
    with sqlite3.connect(DB_NAME) as conn:
        row = conn.execute("SELECT content FROM daily_logs WHERE date=?", (date_str,)).fetchone()
        return row[0] if row else ""

def save_log(date_str, content):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT OR REPLACE INTO daily_logs (date, content) VALUES (?, ?)", (date_str, content))
        
def get_upcoming_deadlines():
    today = datetime.date.today().isoformat()
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            f"""
            SELECT t.title, t.deadline
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            WHERE t.deadline >= ? AND t.completed = 0 AND {_ACTIVE}
            ORDER BY t.deadline ASC
            """,
            (today,),
        ).fetchall()

def get_all_tasks():
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            """
            SELECT t.title, t.start_date, t.deadline, p.name as project_name, t.start_time, t.end_time, t.completed, t.id, t.project_id, t.work_package
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE ifnull(t.archived, 0) = 0 AND ifnull(p.archived, 0) = 0
            ORDER BY t.start_date ASC
            """
        ).fetchall()

def get_upcoming_meeting():
    today = datetime.date.today().isoformat()
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            """
            SELECT t.title, t.deadline, p.name
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE LOWER(t.work_package) = 'meeting' AND t.completed = 0 AND t.deadline >= ?
              AND ifnull(t.archived, 0) = 0 AND ifnull(p.archived, 0) = 0
            ORDER BY t.deadline ASC
            LIMIT 1
            """,
            (today,)
        ).fetchone()

def get_tasks_for_date(date_str):
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            """
            SELECT t.title, p.name, t.start_time, t.end_time, t.completed, t.work_package
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            WHERE ? BETWEEN ifnull(t.start_date, t.deadline) AND t.deadline
              AND ifnull(t.archived, 0) = 0 AND ifnull(p.archived, 0) = 0
            ORDER BY t.completed ASC, t.title COLLATE NOCASE
            """,
            (date_str,),
        ).fetchall()

def get_tasks_for_project_date(project_id, date_str):
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            """
            SELECT id, title, start_time, end_time, completed, work_package
            FROM tasks
            WHERE project_id = ? AND (? BETWEEN ifnull(start_date, deadline) AND deadline)
              AND ifnull(archived, 0) = 0
            ORDER BY completed ASC, title COLLATE NOCASE
            """,
            (project_id, date_str),
        ).fetchall()

def get_dashboard_stats():
    today = datetime.date.today().isoformat()
    base = f"FROM tasks t JOIN projects p ON p.id = t.project_id WHERE {_ACTIVE}"
    with sqlite3.connect(DB_NAME) as conn:
        total = conn.execute(f"SELECT COUNT(*) {base}").fetchone()[0]
        completed = conn.execute(f"SELECT COUNT(*) {base} AND t.completed = 1").fetchone()[0]
        open_tasks = total - completed
        due_today = conn.execute(
            f"SELECT COUNT(*) {base} AND t.deadline = ? AND t.completed = 0",
            (today,),
        ).fetchone()[0]
        overdue = conn.execute(
            f"SELECT COUNT(*) {base} AND t.deadline < ? AND t.completed = 0",
            (today,),
        ).fetchone()[0]
        projects = conn.execute("SELECT COUNT(*) FROM projects WHERE ifnull(archived, 0) = 0").fetchone()[0]

    return {
        "projects": projects,
        "total_tasks": total,
        "open_tasks": open_tasks,
        "completed_tasks": completed,
        "due_today": due_today,
        "overdue": overdue,
    }


# Archive: archived tasks/projects are hidden from every view and search, but kept in the database.

def set_task_archived(task_id, archived=True):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE tasks SET archived=? WHERE id=?", (1 if archived else 0, task_id))

def archive_completed_tasks(project_id):
    """Archive every completed task of a project; returns how many were archived."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.execute(
            "UPDATE tasks SET archived=1 WHERE project_id=? AND completed=1 AND ifnull(archived, 0)=0",
            (project_id,),
        )
        return cursor.rowcount

def set_project_archived(project_id, archived=True):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE projects SET archived=? WHERE id=?", (1 if archived else 0, project_id))

def get_archived_projects():
    """Archived projects as (id, name, start_date, end_date, task_count)."""
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            """
            SELECT p.id, p.name, p.start_date, p.end_date, COUNT(t.id)
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id
            WHERE p.archived = 1
            GROUP BY p.id
            ORDER BY p.name COLLATE NOCASE
            """
        ).fetchall()

def get_archived_tasks():
    """Individually archived tasks of active projects as (id, title, deadline, completed, project_id, project_name)."""
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            """
            SELECT t.id, t.title, t.deadline, t.completed, p.id, p.name
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            WHERE t.archived = 1 AND ifnull(p.archived, 0) = 0
            ORDER BY t.deadline DESC
            """
        ).fetchall()


def _like(query):
    escaped = query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"

def search_tasks(query, limit=100):
    """Tasks whose title, notes, work package or project name contains the query."""
    pattern = _like(query)
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute(
            """
            SELECT t.id, t.title, t.deadline, t.completed, p.id, p.name
            FROM tasks t
            JOIN projects p ON p.id = t.project_id
            WHERE ifnull(t.archived, 0) = 0 AND ifnull(p.archived, 0) = 0
              AND (t.title LIKE ? ESCAPE '!' OR ifnull(t.notes, '') LIKE ? ESCAPE '!'
                   OR ifnull(t.work_package, '') LIKE ? ESCAPE '!' OR p.name LIKE ? ESCAPE '!')
            ORDER BY t.completed ASC, t.deadline ASC
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, limit),
        ).fetchall()

def search_logs(query, limit=50):
    """Daily logs containing the query (matched on their plain text), newest first."""
    needle = query.lower()
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute("SELECT date, content FROM daily_logs ORDER BY date DESC").fetchall()
    matches = []
    for date_str, content in rows:
        plain = log_to_plain(content or "")
        if needle in plain.lower():
            matches.append((date_str, plain))
            if len(matches) >= limit:
                break
    return matches


# Daily-log images: files live in an "attachments" folder next to the database and are
# referenced by relative path, so moving the folder (database + attachments) keeps them working.

def attachments_dir():
    return Path(DB_NAME).parent / "attachments"

def store_attachment(data, suffix=".png"):
    """Save image bytes in the attachments folder; returns the relative path used in log HTML."""
    folder = attachments_dir()
    folder.mkdir(parents=True, exist_ok=True)
    suffix = suffix.lower() if suffix and suffix.startswith(".") else ".png"
    name = f"{uuid.uuid4().hex}{suffix}"
    (folder / name).write_bytes(data)
    return f"attachments/{name}"

def attachment_path(relative):
    return Path(DB_NAME).parent / relative

def is_rich_log(content):
    return content.lstrip()[:15].lower().startswith(("<!doctype html", "<html"))

def log_to_plain(content):
    """Plain-text view of a log (logs containing images are stored as HTML)."""
    if not is_rich_log(content):
        return content
    text = re.sub(r"(?is)<(head|style)\b.*?</\1>", "", content)
    text = re.sub(r"(?i)<img\b[^>]*>", "[image]", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    return html.unescape(text).strip()

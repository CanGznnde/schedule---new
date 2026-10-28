# Personal Work Schedule

A local-first desktop planner for organising work across several projects. It combines a task list, a calendar, a Gantt chart and a daily log in one window. Everything is stored in a single SQLite file on your machine, with no account, server or network access.

Built with Python, PySide6 (Qt) and SQLite.

![Dashboard](docs/screenshots/dashboard.png)

## Features

- **Dashboard** – counts of projects, open, completed, due-today and overdue tasks, a banner for your next meeting, and a list of upcoming deadlines (due-today items in red).
- **Projects** – create projects with optional start/end dates, rename them, and drag them in the sidebar to reorder.
- **Tasks** – each task has a title, start date, deadline, optional start/end time and an optional *work package* used for grouping. Tasks can be checked off and can have subtasks.
- **Gantt chart** – per-project timeline with tasks grouped by work package. Tasks with the work package `Meeting` are treated as meetings and surfaced on the dashboard.
- **Calendar** – month view with markers on days that have tasks, plus the tasks for the selected day.
- **Daily log** – free-text notes saved per day.
- **Reminders** – a popup on launch lists tasks due today.

## Screenshots

| Tasks | Gantt chart |
|---|---|
| ![Tasks](docs/screenshots/tasks.png) | ![Gantt chart](docs/screenshots/gantt.png) |

| Calendar | Daily log |
|---|---|
| ![Calendar](docs/screenshots/calendar.png) | ![Daily log](docs/screenshots/daily-log.png) |

![Projects overview](docs/screenshots/projects.png)

The screenshots use made-up sample data.

## Getting started

Requirements: Python 3.10+ and the packages in `requirements.txt`.

```bash
pip install -r requirements.txt
python main.py
```

### Where is my data?

Your data lives in `planner.db`, in the same folder as `main.py` (or next to the `.exe` when running the packaged build). It is created automatically on first launch, and older databases are migrated in place when new columns are added.

To back up or move your schedule, copy that one file. It is excluded from git so personal data is never committed.

> **Note:** if `planner.db` is missing, the app falls back to the first `*.db` file it finds in its folder, then in the current working directory. Avoid keeping unrelated `.db` files next to it.

## Build a standalone executable (Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name PersonalWorkSchedule main.py
```

The executable is written to `dist/`. Place a `planner.db` next to it to bring existing data, otherwise a fresh one is created. If the build misses SQLite DLLs (common with Anaconda Python), add them with `--add-binary`.

## Project layout

| File | Purpose |
|---|---|
| `main.py` | Main window, sidebar, project management and application entry point |
| `views.py` | UI views: dashboard, projects overview, task list, Gantt chart, calendar, daily log |
| `database.py` | SQLite schema, migrations and all queries |
| `docs/screenshots/` | Images used in this README |

# Personal Work Schedule

A desktop planner built with PySide6 and SQLite. It has a dashboard, calendar, task list, daily log and a projects overview.

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt`

## Run

```bash
pip install -r requirements.txt
python main.py
```

The app stores its data in `planner.db` next to `main.py` (or next to the executable when frozen). The file is created automatically on first launch and is not tracked by git.

## Build a standalone executable

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name PersonalWorkSchedule main.py
```

The result is in `dist/`. If the build misses SQLite DLLs (common with Anaconda), add them with `--add-binary`.

## Project layout

- `main.py` – main window and application entry point
- `views.py` – UI views (dashboard, calendar, tasks, daily log, projects)
- `database.py` – SQLite access layer

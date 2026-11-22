"""
SQL-хранилище планировщика (база данных SQLite).

Реляционная схема: years -> months -> days -> events.
Модуль совместим с существующей базой dataBases/testDataBase.db.
"""
import os
import sqlite3
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("PLANNER_DB", os.path.join(BASE_DIR, "dataBases", "testDataBase.db"))

WEEK_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def is_leap_year(year):
    return year % 400 == 0 or (year % 100 != 0 and year % 4 == 0)


DAYS_IN_MONTH_COMMON = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                        7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def days_in_month(year, month):
    if month == 2 and is_leap_year(year):
        return 29
    return DAYS_IN_MONTH_COMMON[month]


def weekday_of(year, month, day):
    """0 = monday ... 6 = sunday (isoformat)."""
    return date(year, month, day).weekday()


LEGACY_TABLES = ["years", "months", "days", "events"]


def _migrate_legacy(conn):
    """Старая схема (name TEXT, date_str TEXT) несовместима — пересоздаём таблицы."""
    rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()
    existing = {r["name"]: (r["sql"] or "") for r in rows if r["name"] in LEGACY_TABLES}
    if not existing:
        return
    needs_migration = any(
        ("year_number" not in existing.get(t, "")) if t == "years"
        else (t in existing and "year_number" not in existing[t])
        for t in LEGACY_TABLES
    )
    if needs_migration:
        conn.execute("PRAGMA foreign_keys = OFF")
        for t in reversed(LEGACY_TABLES):
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")


SCHEMA = """
CREATE TABLE IF NOT EXISTS years (
    year_number INTEGER PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS months (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_number INTEGER NOT NULL,
    month_number INTEGER NOT NULL,
    first_day_weekday INTEGER DEFAULT 0,
    UNIQUE (year_number, month_number),
    FOREIGN KEY (year_number) REFERENCES years (year_number) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_number INTEGER NOT NULL,
    month_number INTEGER NOT NULL,
    day_number INTEGER NOT NULL,
    weekday INTEGER NOT NULL,
    UNIQUE (year_number, month_number, day_number),
    FOREIGN KEY (year_number, month_number) REFERENCES months (year_number, month_number) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_id INTEGER NOT NULL,
    start_time INTEGER NOT NULL,      -- минуты от начала суток (0..1439)
    duration_time INTEGER NOT NULL,   -- длительность в минутах
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    FOREIGN KEY (day_id) REFERENCES days (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_events_day ON events (day_id);
CREATE INDEX IF NOT EXISTS idx_days_date ON days (year_number, month_number, day_number);
"""


class Database:
    """Тонкая обёртка над sqlite3 с доменными методами календаря."""

    def __init__(self, path=None):
        self.path = path or DB_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("PRAGMA journal_mode = WAL")  # конкурентное чтение/запись
        except sqlite3.OperationalError:
            pass
        self.conn.execute("PRAGMA foreign_keys = ON")
        _migrate_legacy(self.conn)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- вспомогательное ----------
    def _ensure_day(self, year, month, day):
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO years (year_number) VALUES (?)", (year,))
        wd_first = weekday_of(year, month, 1)
        cur.execute(
            "INSERT OR IGNORE INTO months (year_number, month_number, first_day_weekday) VALUES (?, ?, ?)",
            (year, month, wd_first))
        wd = weekday_of(year, month, day)
        cur.execute(
            "INSERT OR IGNORE INTO days (year_number, month_number, day_number, weekday) VALUES (?, ?, ?, ?)",
            (year, month, day, wd))
        row = cur.execute(
            "SELECT id FROM days WHERE year_number=? AND month_number=? AND day_number=?",
            (year, month, day)).fetchone()
        return row["id"]

    # ---------- события ----------
    def add_event(self, year, month, day, start_time, duration_time, name, description=""):
        """Добавляет событие, если оно не пересекается с существующими. Возвращает id или None."""
        if not (0 <= start_time < 1440 and duration_time > 0 and start_time + duration_time <= 1440):
            raise ValueError("Некорректное время события")
        max_day = days_in_month(year, month)
        if not (1 <= day <= max_day):
            raise ValueError("Некорректный день месяца")
        day_id = self._ensure_day(year, month, day)
        overlap = self.conn.execute(
            """SELECT COUNT(*) c FROM events WHERE day_id=?
               AND start_time < ? AND start_time + duration_time > ?""",
            (day_id, start_time + duration_time, start_time)).fetchone()["c"]
        if overlap:
            return None
        cur = self.conn.execute(
            "INSERT INTO events (day_id, start_time, duration_time, name, description) VALUES (?, ?, ?, ?, ?)",
            (day_id, start_time, duration_time, name, description))
        self.conn.commit()
        return cur.lastrowid

    def rm_event(self, event_id=None, year=None, month=None, day=None, start_time=None):
        """Удаление по id события либо по (дата + start_time)."""
        if event_id is not None:
            cur = self.conn.execute("DELETE FROM events WHERE id=?", (event_id,))
        else:
            cur = self.conn.execute(
                """DELETE FROM events WHERE day_id=(
                       SELECT id FROM days WHERE year_number=? AND month_number=? AND day_number=?)
                   AND start_time=?""",
                (year, month, day, start_time))
        self.conn.commit()
        return cur.rowcount > 0

    def get_events(self, year=None, month=None, day=None):
        sql = """SELECT e.id, e.name, e.description, e.start_time, e.duration_time,
                        d.year_number, d.month_number, d.day_number, d.weekday
                 FROM events e JOIN days d ON e.day_id = d.id WHERE 1=1"""
        params = []
        if year is not None:
            sql += " AND d.year_number=?"; params.append(year)
        if month is not None:
            sql += " AND d.month_number=?"; params.append(month)
        if day is not None:
            sql += " AND d.day_number=?"; params.append(day)
        sql += " ORDER BY d.year_number, d.month_number, d.day_number, e.start_time"
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def find_events(self, text):
        """Поиск по названию и описанию."""
        like = f"%{text}%"
        rows = self.conn.execute(
            """SELECT e.id, e.name, e.description, e.start_time, e.duration_time,
                      d.year_number, d.month_number, d.day_number, d.weekday
               FROM events e JOIN days d ON e.day_id=d.id
               WHERE e.name LIKE ? OR e.description LIKE ?
               ORDER BY d.year_number, d.month_number, d.day_number, e.start_time""",
            (like, like)).fetchall()
        return [dict(r) for r in rows]

    def day_summary(self, year, month, day):
        events = self.get_events(year, month, day)
        busy = sum(e["duration_time"] for e in events)
        return {"date": f"{year:04d}-{month:02d}-{day:02d}",
                "weekday": WEEK_DAYS[weekday_of(year, month, day)],
                "events_count": len(events),
                "busy_minutes": busy,
                "free_minutes": 1440 - busy}

    def stats(self):
        total = self.conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
        days = self.conn.execute("SELECT COUNT(*) c FROM days").fetchone()["c"]
        avg = self.conn.execute(
            """SELECT AVG(cnt) FROM (SELECT COUNT(*) cnt FROM events GROUP BY day_id)""").fetchone()[0]
        return {"total_events": total, "days_with_calendar": days,
                "avg_events_per_busy_day": round(avg, 2) if avg else 0}

    def close(self):
        self.conn.close()

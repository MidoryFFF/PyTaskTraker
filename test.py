"""Интеграционный тест: SQL-хранилище + инструменты ИИ."""
import os
os.environ["PLANNER_DB"] = os.path.join(os.path.dirname(__file__), "dataBases", "test_run.db")

from src.database import Database
from Instruments import call_tool

db = Database()
assert db.add_event(2026, 1, 1, 7 * 60 + 30, 60, "Что-то", "что-то будет")
assert db.add_event(2026, 1, 1, 9 * 60 + 30, 60, "Что-то1", "что-то будет1")
assert db.add_event(2026, 1, 1, 8 * 60 + 30, 120, "пересечение", "") is None  # накладка
assert len(db.get_events(2026, 1)) == 2

r = call_tool("add_event", {"date_": "2026-05-04", "time": "18:30", "duration": "1:30",
                            "name": "Встреча", "description": "с инструментами"})
assert "Создано" in r["result"], r
assert call_tool("free_slots", {"date_": "2026-05-04", "min_duration": 60})["result"] == ["00:00–18:30", "20:00–24:00"]
assert call_tool("search_events", {"query": "Встреча"})["result"]
assert call_tool("day_summary", {"date_": "2026-05-04"})["result"]["busy_minutes"] == 90
print("Все тесты пройдены ✔")

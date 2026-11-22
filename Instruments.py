"""
Инструментарий для ИИ (AI tools / function calling).

Каждый инструмент — обычная Python-функция, задекорированная @tool.
Из декораторов генерируется JSON-схема в формате Ollama / OpenAI tool-calling,
а реестр выполняет вызовы по имени с валидацией аргументов.
"""
import inspect
import json
import re
from datetime import date, timedelta

from src.database import Database, WEEK_DAYS

# ---------- реестр инструментов ----------
TOOLS = {}          # name -> {"func": callable, "schema": dict}
_db_singleton = None


def get_db():
    global _db_singleton
    if _db_singleton is None:
        _db_singleton = Database()
    return _db_singleton


def tool(name=None, description=None, parameters=None):
    """Декоратор: регистрирует функцию как инструмент ИИ."""
    def wrapper(func):
        tool_name = name or func.__name__
        sig = inspect.signature(func)
        props, required = {}, []
        for pname, p in sig.parameters.items():
            if pname.startswith("_"):
                continue
            typ = {int: "integer", float: "number", str: "string",
                   bool: "boolean", list: "array", dict: "object"}.get(p.annotation, "string")
            entry = {"type": typ}
            if p.default is not inspect.Parameter.empty:
                entry["default"] = p.default
            else:
                required.append(pname)
            props[pname] = entry
        schema = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description or (func.__doc__ or "").strip().splitlines()[0],
                "parameters": {"type": "object", "properties": props, "required": required},
            },
        }
        TOOLS[tool_name] = {"func": func, "schema": schema}
        return func
    return wrapper


def get_tool_schemas():
    """Список JSON-схем всех инструментов (для передачи модели)."""
    return [t["schema"] for t in TOOLS.values()]


def call_tool(name, arguments):
    """Выполняет инструмент по имени. arguments — dict или JSON-строка."""
    if isinstance(arguments, str):
        arguments = json.loads(arguments or "{}")
    if name not in TOOLS:
        return {"error": f"Неизвестный инструмент: {name}"}
    try:
        result = TOOLS[name]["func"](**arguments)
        return {"result": result}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


# ---------- разбор дат ----------
_MONTHS = {"январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
           "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
           "januar": 1, "februar": 2, "march": 3, "april": 4, "may": 5, "june": 6,
           "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}


def parse_time(text):
    """'18:30', '18.30', '18', '9:05' -> минуты от начала суток."""
    m = re.match(r"^(\d{1,2})[:.\s]?(\d{1,2})?$", str(text).strip())
    if not m:
        raise ValueError(f"Не удалось разобрать время: {text}")
    h = int(m.group(1))
    mi = int(m.group(2) or 0)
    if not (0 <= h < 24 and 0 <= mi < 60):
        raise ValueError(f"Некорректное время: {text}")
    return h * 60 + mi


def parse_duration(text):
    """'60', '1:30', '1.5h', '90 min', '2ч' -> минуты."""
    s = str(text).strip().lower().replace("мин", "min").replace("час", "h").replace("ч", "h")
    m = re.match(r"^(\d+[:.]\d+|\d+)\s*(h|hours?|min|minutes?)?$", s)
    if not m:
        raise ValueError(f"Не удалось разобрать длительность: {text}")
    num = m.group(1).replace(",", ".")
    unit = m.group(2) or "min"
    if ":" in num:  # '1:30' -> 1 час 30 минут
        h, mi = num.split(":")
        return int(h) * 60 + int(mi)
    val = float(num)
    minutes = val * 60 if unit.startswith("h") else val
    return int(minutes)


def parse_date(text):
    """'сегодня', 'завтра', '2026-11-22', '22.11', '22 ноября' -> date."""
    s = str(text).strip().lower()
    today = date.today()
    if s in ("сегодня", "today", ""):
        return today
    if s in ("завтра", "tomorrow"):
        return today + timedelta(days=1)
    if s in ("послезавтра", "day after tomorrow"):
        return today + timedelta(days=2)
    if s in ("вчера", "yesterday"):
        return today - timedelta(days=1)
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?$", s)
    if m:
        y = m.group(3)
        year = int(y) if y else today.year
        if year < 100:
            year += 2000
        return date(year, int(m.group(2)), int(m.group(1)))
    m = re.match(r"^(\d{1,2})\s*([а-яa-z]+)$", s)
    if m:
        word = m.group(2)
        for key, num in _MONTHS.items():
            if word.startswith(key):
                return date(today.year, num, int(m.group(1)))
    raise ValueError(f"Не удалось разобрать дату: {text}")


def fmt_event(e):
    st, dur = e["start_time"], e["duration_time"]
    return (f"[id:{e['id']}] {e['year_number']}-{e['month_number']:02d}-{e['day_number']:02d} "
            f"{WEEK_DAYS[e['weekday']]} {st//60:02d}:{st%60:02d}–{(st+dur)//60:02d}:{(st+dur)%60:02d} "
            f"«{e['name']}» — {e['description']}")


# ---------- инструменты ----------
@tool(description="Показать все события планировщика за период (ISO-даты, включительно).")
def list_events(date_from: str = "", date_to: str = ""):
    db = get_db()
    events = db.get_events()
    if date_from:
        d = parse_date(date_from)
        events = [e for e in events if (e["year_number"], e["month_number"], e["day_number"]) >= (d.year, d.month, d.day)]
    if date_to:
        d = parse_date(date_to)
        events = [e for e in events if (e["year_number"], e["month_number"], e["day_number"]) <= (d.year, d.month, d.day)]
    return [fmt_event(e) for e in events]


@tool(description="Добавить событие. time/duration принимают человекочитаемые форматы ('18:30', '1:30', '2 часа').")
def add_event(date_: str = "сегодня", time: str = "9:00", duration: str = "60",
              name: str = "", description: str = ""):
    d = parse_date(date_)
    ev_id = get_db().add_event(d.year, d.month, d.day, parse_time(time),
                               parse_duration(duration), name or "Событие", description)
    if ev_id is None:
        return "Накладка: в это время уже есть событие."
    return f"Создано событие id={ev_id} на {d.isoformat()} {time} ({duration} мин): {name}"


@tool(description="Удалить событие по его id.")
def delete_event(event_id: int = 0):
    return "Удалено." if get_db().rm_event(event_id=event_id) else "Событие не найдено."


@tool(description="Найти события по тексту в названии или описании.")
def search_events(query: str = ""):
    return [fmt_event(e) for e in get_db().find_events(query)]


@tool(description="Сводка по дню: количество событий, занято/свободно минут.")
def day_summary(date_: str = "сегодня"):
    d = parse_date(date_)
    return get_db().day_summary(d.year, d.month, d.day)


@tool(description="Найти свободные интервалы (не менее min_duration минут) на указанную дату.")
def free_slots(date_: str = "сегодня", min_duration: int = 60):
    d = parse_date(date_)
    events = get_db().get_events(d.year, d.month, d.day)
    busy = sorted((e["start_time"], e["start_time"] + e["duration_time"]) for e in events)
    slots, cur = [], 0
    for b_start, b_end in busy:
        if b_start - cur >= min_duration:
            slots.append(f"{cur//60:02d}:{cur%60:02d}–{b_start//60:02d}:{b_start%60:02d}")
        cur = max(cur, b_end)
    if 1440 - cur >= min_duration:
        slots.append(f"{cur//60:02d}:{cur%60:02d}–24:00")
    return slots


@tool(description="Общая статистика планировщика.")
def planner_stats():
    return get_db().stats()


if __name__ == "__main__":
    print(json.dumps(get_tool_schemas(), ensure_ascii=False, indent=2))

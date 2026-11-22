"""
Точка входа планировщика.

Режимы:
  python StartPoint.py                 — CLI-меню в терминале
  python StartPoint.py --web [--port]  — локальный веб-интерфейс (Flask)
  python StartPoint.py --ai            — чат с локальной моделью (Ollama) в терминале
"""
import argparse
from datetime import date, timedelta

from Instruments import get_db, parse_date, parse_time, parse_duration, free_slots, day_summary
from src.database import WEEK_DAYS


def fmt_min(m):
    return f"{m//60:02d}:{m%60:02d}"


def show_events(year=None, month=None, day=None):
    events = get_db().get_events(year, month, day)
    if not events:
        print("Событий нет.")
        return
    for e in events:
        print(f"  id:{e['id']} {e['year_number']}-{e['month_number']:02d}-{e['day_number']:02d} "
              f"({WEEK_DAYS[e['weekday']]}) {fmt_min(e['start_time'])}-{fmt_min(e['start_time']+e['duration_time'])} "
              f"«{e['name']}» {e['description']}")


def cli_menu():
    while True:
        print("\n=== Планировщик ===\n1) события за день\n2) события за месяц\n3) добавить событие\n"
              "4) удалить событие\n5) сводка дня и свободные слоты\n6) статистика\n0) выход")
        c = input("> ").strip()
        try:
            if c == "1":
                d = parse_date(input("Дата (ГГГГ-ММ-ДД / сегодня / завтра): "))
                show_events(d.year, d.month, d.day)
            elif c == "2":
                y = int(input("Год: ")); m = int(input("Месяц (1-12): "))
                show_events(y, m)
            elif c == "3":
                d = parse_date(input("Дата: "))
                st = parse_time(input("Начало (напр. 18:30): "))
                dur = parse_duration(input("Длительность (напр. 1:30 или 90): "))
                name = input("Название: ")
                desc = input("Описание: ")
                ev_id = get_db().add_event(d.year, d.month, d.day, st, dur, name, desc)
                print("Создано, id =", ev_id if ev_id is not None else "НАКЛАДКА!")
            elif c == "4":
                print("Удалено." if get_db().rm_event(event_id=int(input("id события: "))) else "Не найдено.")
            elif c == "5":
                d = parse_date(input("Дата: "))
                print(day_summary(d.isoformat()))
                print("Свободно >=30 мин:", free_slots(d.isoformat(), 30))
            elif c == "6":
                print(get_db().stats())
            elif c == "0":
                break
        except Exception as e:  # noqa: BLE001
            print("Ошибка:", e)


def ai_cli():
    from AI import OllamaClient, ContextManager
    client = OllamaClient(model=__import__("os").environ.get("OLLAMA_MODEL", "llama3.1"))
    if not client.is_available():
        print("Ollama недоступен. Запустите `ollama serve` (и `ollama pull llama3.1`).")
        return
    ctx = ContextManager(client)
    print("Чат с ИИ (инструменты подключены). 'exit' — выход.")
    while True:
        msg = input("Вы: ").strip()
        if msg.lower() in ("exit", "quit", ""):
            break
        out = ctx.ask(msg)
        for t in out["trace"]:
            print(f"  [tool] {t['tool']}({t['args']})")
        print("ИИ:", out["answer"])


def main():
    p = argparse.ArgumentParser(description="Планировщик с SQL-хранилищем и ИИ")
    p.add_argument("--web", action="store_true", help="запустить локальный веб-интерфейс")
    p.add_argument("--ai", action="store_true", help="запустить ИИ-чат в терминале")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args()
    if args.web:
        from Ui import run
        print(f"Веб-интерфейс: http://{args.host}:{args.port}")
        run(host=args.host, port=args.port)
    elif args.ai:
        ai_cli()
    else:
        cli_menu()


if __name__ == "__main__":
    main()

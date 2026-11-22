"""
Локальный веб-интерфейс (Flask) для планировщика.

Запуск:  python StartPoint.py --web
Страницы:
  /            — календарь (месяц/неделя/день) + формы событий
  /ai          — чат с локальной моделью через Ollama (с инструментами)
API:
  GET  /api/events?year=&month=&day=
  POST /api/events          {date, time, duration, name, description}
  DELETE /api/events/<id>
  GET  /api/day/<date>      сводка дня + свободные слоты
  POST /api/ai/chat         {message} -> {answer, trace}
  GET  /api/ai/status       доступность Ollama и список моделей
"""
import json
import os

from flask import Flask, jsonify, render_template, request

from Instruments import get_db, parse_date, parse_time, parse_duration, free_slots, day_summary
from AI import OllamaClient, ContextManager

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))

_ai_state = {"client": None, "ctx": None}


def get_ctx():
    if _ai_state["ctx"] is None:
        client = OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1"),
                              num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", "4096")))
        _ai_state["client"] = client
        _ai_state["ctx"] = ContextManager(client)
    return _ai_state["ctx"]


# ---------------------------- страницы ----------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ai")
def ai_page():
    return render_template("ai.html")


# ---------------------------- события ----------------------------
@app.route("/api/events", methods=["GET"])
def api_events():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    day = request.args.get("day", type=int)
    return jsonify(get_db().get_events(year, month, day))


@app.route("/api/events", methods=["POST"])
def api_add_event():
    data = request.get_json(force=True)
    try:
        d = parse_date(data.get("date", ""))
        start = parse_time(data.get("time", "9:00"))
        dur = parse_duration(data.get("duration", "60"))
        ev_id = get_db().add_event(d.year, d.month, d.day, start, dur,
                                   data.get("name", "Событие"), data.get("description", ""))
        if ev_id is None:
            return jsonify({"error": "Накладка: в это время уже есть событие"}), 409
        return jsonify({"id": ev_id}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/events/<int:event_id>", methods=["DELETE"])
def api_delete_event(event_id):
    return jsonify({"deleted": get_db().rm_event(event_id=event_id)})


@app.route("/api/day/<path:date_str>")
def api_day(date_str):
    d = parse_date(date_str)
    return jsonify({"summary": day_summary(d.isoformat()),
                    "free": free_slots(d.isoformat(), 30)})


# ---------------------------- ИИ ----------------------------
@app.route("/api/ai/status")
def api_ai_status():
    ctx = get_ctx()
    available = ctx.client.is_available()
    models = []
    if available:
        try:
            models = ctx.client.list_models()
        except Exception:  # noqa: BLE001
            pass
    return jsonify({"ollama_available": available, "models": models,
                    "model": ctx.client.model, "num_ctx": ctx.client.num_ctx})


@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat():
    message = (request.get_json(force=True) or {}).get("message", "").strip()
    if not message:
        return jsonify({"error": "Пустое сообщение"}), 400
    ctx = get_ctx()
    if not ctx.client.is_available():
        return jsonify({"answer": "Ollama недоступен. Запустите `ollama serve` и загрузите модель.",
                        "trace": [], "offline": True}), 503
    try:
        out = ctx.ask(message)
        return jsonify({"answer": out["answer"], "trace": out["trace"]})
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/reset", methods=["POST"])
def api_ai_reset():
    _ai_state["ctx"] = None
    return jsonify({"ok": True})


def run(host="127.0.0.1", port=8080, debug=False):
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run(debug=True)

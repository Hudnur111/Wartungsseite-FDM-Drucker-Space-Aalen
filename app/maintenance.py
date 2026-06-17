from __future__ import annotations

from datetime import date, datetime

from .database import rows


def due_items(conn) -> list[dict]:
    devices = rows(conn, "SELECT * FROM devices WHERE active = 1 ORDER BY sort_order, name")
    tasks = rows(conn, "SELECT * FROM tasks WHERE active = 1 ORDER BY sort_order, title")
    logs = rows(conn, "SELECT * FROM logs ORDER BY id DESC")
    latest = {}
    for log in logs:
        key = (log["device_id"], log["task_id"])
        current = latest.get(key)
        if not current or (log["done_on"], log["id"]) > (current["done_on"], current["id"]):
            latest[key] = log

    today = date.today()
    items = []
    for device in devices:
        current_hours = device.get("current_print_hours")
        if current_hours is None:
            device_logs = [item["print_hours"] for item in logs if item["device_id"] == device["id"] and item["print_hours"] is not None]
            current_hours = max(device_logs) if device_logs else None
        for task in tasks:
            if task["applies_to"] not in {"all", device["kind"]}:
                continue
            if not task["cadence_days"] and not task["cadence_hours"]:
                continue
            log = latest.get((device["id"], task["id"]))
            status = None
            detail = ""
            if not log:
                status = "open"
                detail = "kein Eintrag"
            elif task["cadence_hours"] and log["print_hours"] is not None and current_hours is not None:
                age = max(0, int(current_hours) - int(log["print_hours"]))
                remaining = int(task["cadence_hours"]) - age
                if age > int(task["cadence_hours"]):
                    status = "due"
                elif remaining <= 25:
                    status = "due-soon"
                detail = f"{age} h seit letzter Wartung"
            elif task["cadence_hours"] and not task["cadence_days"]:
                status = "open"
                detail = "Druckstunden fehlen"
            else:
                try:
                    done = datetime.strptime(log["done_on"], "%Y-%m-%d").date()
                except (TypeError, ValueError):
                    status = "open"
                    detail = "Datum prüfen"
                else:
                    age = (today - done).days
                    remaining = int(task["cadence_days"]) - age
                    if age > int(task["cadence_days"]):
                        status = "due"
                    elif remaining <= 7:
                        status = "due-soon"
                    detail = f"{age} Tage seit letzter Wartung"
            if status in {"open", "due", "due-soon"}:
                items.append(
                    {
                        "device_id": device["id"],
                        "device": device["name"],
                        "task_id": task["id"],
                        "task": task["title"],
                        "level": task["level"],
                        "status": status,
                        "detail": detail,
                        "last_done": log["done_on"] if log else "",
                    }
                )
    order = {"due": 0, "open": 1, "due-soon": 2}
    return sorted(items, key=lambda item: (order.get(item["status"], 9), item["device"], item["task"]))


def teams_payload(items: list[dict]) -> dict:
    if not items:
        return {"text": "Wartung FDM Space: Aktuell sind keine Wartungen fällig."}

    lines = ["Wartung FDM Space: Fällige und bald fällige Wartungen", ""]
    for item in items[:25]:
        label = {"due": "FÄLLIG", "open": "OFFEN", "due-soon": "BALD"}[item["status"]]
        lines.append(f"- {label}: {item['device']} - {item['task']} ({item['detail']})")
    if len(items) > 25:
        lines.append(f"- plus {len(items) - 25} weitere Einträge")
    return {"text": "\n".join(lines)}

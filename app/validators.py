from __future__ import annotations

import re
from datetime import date, datetime


ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


def valid_date(value: str, label: str, allow_future: bool = False) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} muss ein gültiges Datum sein.") from exc
    if not allow_future and parsed > date.today():
        raise ValueError(f"{label} darf nicht in der Zukunft liegen.")
    return parsed.isoformat()


def valid_id(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not ID_RE.fullmatch(normalized):
        raise ValueError(f"{label} darf nur Kleinbuchstaben, Zahlen, Bindestriche und Unterstriche enthalten.")
    return normalized


def optional_int(value, label: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} muss eine ganze Zahl sein.") from exc
    if parsed < 0:
        raise ValueError(f"{label} darf nicht negativ sein.")
    return parsed


def task_applies_to_device(task: dict, device: dict) -> bool:
    return task["applies_to"] == "all" or task["applies_to"] == device["kind"]

import csv
import io
import json

from flask import Blueprint, Response, current_app
from flask_login import current_user, login_required
from sqlalchemy import select

from ..extensions import db
from ..models import Habit, HabitLog
from ..services import timeutil

bp = Blueprint("export", __name__, url_prefix="/export")


def _csv_safe(value: str) -> str:
    """Cegah CSV injection.

    Nama habit diisi pengguna. Kalau diawali = + - @ , Excel menganggapnya rumus
    saat file dibuka. Awalan tanda kutip membuatnya dibaca sebagai teks biasa.
    """
    if value and value[0] in "=+-@\t\r":
        return "'" + value
    return value


@bp.get("/csv")
@login_required
def export_csv():
    rows = db.session.execute(
        select(HabitLog.log_date, Habit.name, Habit.category, HabitLog.status, Habit.is_active)
        .join(Habit, Habit.id == HabitLog.habit_id)
        .where(Habit.user_id == current_user.id)
        .order_by(HabitLog.log_date, Habit.name)
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["tanggal", "habit", "kategori", "status", "habit_aktif"])
    for log_date, name, category, status, is_active in rows:
        writer.writerow([log_date.isoformat(), _csv_safe(name), category, status, "ya" if is_active else "tidak"])

    today = timeutil.local_today(current_app.config["APP_TZ"])
    return Response(
        "﻿" + buffer.getvalue(),  # BOM supaya Excel membaca UTF-8 dengan benar
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="habit-log-{today.isoformat()}.csv"'},
    )


@bp.get("/json")
@login_required
def export_json():
    habits = db.session.scalars(
        select(Habit).where(Habit.user_id == current_user.id).order_by(Habit.created_at, Habit.id)
    ).all()
    payload = {
        "habits": [
            {
                "name": h.name,
                "description": h.description,
                "category": h.category,
                "is_active": h.is_active,
                "created_at": h.created_at.isoformat(),
                "logs": [
                    {"date": log.log_date.isoformat(), "status": log.status}
                    for log in sorted(h.logs, key=lambda l: l.log_date)
                ],
            }
            for h in habits
        ]
    }
    today = timeutil.local_today(current_app.config["APP_TZ"])
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="habit-log-{today.isoformat()}.json"'},
    )

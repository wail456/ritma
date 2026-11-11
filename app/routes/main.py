import random

from flask import Blueprint, current_app, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..forms import HabitForm
from ..services import timeutil, tracker

bp = Blueprint("main", __name__)


def _sample_columns(weeks: int = 18) -> list[list[int]]:
    """Level warna acak (tetap, seed 11) untuk gambar contoh di landing page.

    Murni hiasan dan diberi keterangan "Contoh" di halaman; tidak ada hubungannya
    dengan data pengguna mana pun. Peluang level tinggi naik tiap minggu supaya
    terlihat seperti kebiasaan yang makin konsisten.
    """
    rng = random.Random(11)
    columns = []
    for w in range(weeks):
        boost = w / (weeks - 1)
        column = []
        for _ in range(7):
            roll = rng.random() - boost * 0.45
            column.append(0 if roll > 0.75 else 1 if roll > 0.5 else 2 if roll > 0.25 else 3)
        columns.append(column)
    return columns


@bp.get("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html", sample=_sample_columns())


@bp.get("/dashboard")
@login_required
def dashboard():
    data = tracker.build_dashboard(current_user.id)
    greeting = timeutil.greeting(current_app.config["APP_TZ"])
    return render_template("dashboard.html", data=data, habit_form=HabitForm(), greeting=greeting)


@bp.get("/healthz")
def healthz():
    # Sengaja tidak menyentuh database: health check yang sering dipanggil akan
    # menjaga compute Neon tetap menyala terus dan menghabiskan jatah gratisnya.
    return jsonify(status="ok")

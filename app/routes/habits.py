from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from ..extensions import db
from ..forms import HabitForm
from ..models import STATUSES, Habit
from ..services import timeutil, tracker

bp = Blueprint("habits", __name__, url_prefix="/habits")


def _owned_or_404(habit_id: int) -> Habit:
    """Ambil habit milik pengguna yang sedang login.

    Habit milik orang lain mengembalikan 404, bukan 403. Dengan 403 penyerang tahu
    bahwa ID itu ada; dengan 404 ID yang ada dan yang tidak ada tampak sama.
    """
    habit = db.session.get(Habit, habit_id)
    if habit is None or habit.user_id != current_user.id:
        abort(404)
    return habit


def _active_count() -> int:
    return db.session.scalar(
        select(func.count(Habit.id)).where(Habit.user_id == current_user.id, Habit.is_active.is_(True))
    )


def _flash_form_errors(form) -> None:
    for errors in form.errors.values():
        for message in errors:
            flash(message, "error")


@bp.get("/")
@login_required
def index():
    """Halaman kelola: semua habit aktif + tombol ekspor data."""
    habits = db.session.scalars(
        select(Habit)
        .where(Habit.user_id == current_user.id, Habit.is_active.is_(True))
        .order_by(Habit.created_at.asc(), Habit.id.asc())
    ).all()
    return render_template(
        "habits/index.html", habits=habits, limit=current_app.config["MAX_ACTIVE_HABITS"]
    )


@bp.post("/")
@login_required
def create():
    form = HabitForm()
    if not form.validate_on_submit():
        _flash_form_errors(form)
        return redirect(url_for("main.dashboard"))
    if _active_count() >= current_app.config["MAX_ACTIVE_HABITS"]:
        flash(f"Maksimal {current_app.config['MAX_ACTIVE_HABITS']} habit aktif. Arsipkan yang lama dulu.", "error")
        return redirect(url_for("main.dashboard"))

    habit = Habit(
        user_id=current_user.id,
        name=form.name.data,
        description=form.description.data or None,
        category=form.category.data,
    )
    db.session.add(habit)
    db.session.commit()
    flash(f"Habit “{habit.name}” ditambahkan.", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/<int:habit_id>/edit", methods=["GET", "POST"])
@login_required
def edit(habit_id: int):
    habit = _owned_or_404(habit_id)
    form = HabitForm(obj=habit)
    if form.validate_on_submit():
        habit.name = form.name.data
        habit.description = form.description.data or None
        habit.category = form.category.data
        db.session.commit()
        flash("Perubahan disimpan.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("habits/edit.html", form=form, habit=habit)


@bp.post("/<int:habit_id>/archive")
@login_required
def archive(habit_id: int):
    habit = _owned_or_404(habit_id)
    habit.is_active = False
    db.session.commit()
    flash(f"“{habit.name}” diarsipkan. Riwayatnya tetap tersimpan.", "info")
    return redirect(url_for("main.dashboard"))


@bp.post("/<int:habit_id>/restore")
@login_required
def restore(habit_id: int):
    habit = _owned_or_404(habit_id)
    if _active_count() >= current_app.config["MAX_ACTIVE_HABITS"]:
        flash("Batas habit aktif tercapai. Arsipkan yang lain dulu.", "error")
    else:
        habit.is_active = True
        db.session.commit()
        flash(f"“{habit.name}” aktif kembali.", "success")
    return redirect(url_for("habits.archived"))


@bp.get("/archived")
@login_required
def archived():
    habits = db.session.scalars(
        select(Habit)
        .where(Habit.user_id == current_user.id, Habit.is_active.is_(False))
        .order_by(Habit.created_at.desc())
    ).all()
    return render_template("habits/archived.html", habits=habits)


@bp.post("/<int:habit_id>/log")
@login_required
def log(habit_id: int):
    """Toggle status habit untuk HARI INI.

    Dipanggil lewat HTMX (mengembalikan potongan HTML: baris habit + kartu ringkasan
    + heatmap) atau lewat form biasa tanpa JavaScript (redirect ke dashboard).
    """
    habit = _owned_or_404(habit_id)
    if not habit.is_active:
        abort(409)  # habit yang diarsipkan tidak bisa dicentang

    status = request.form.get("status")
    if status not in STATUSES:
        abort(400)

    today = timeutil.local_today(current_app.config["APP_TZ"])
    new_status = tracker.set_log(habit, today, status)

    if request.headers.get("HX-Request"):
        data = tracker.build_dashboard(current_user.id, today)
        return render_template("partials/toggle_response.html", habit=habit, status=new_status, data=data)
    return redirect(url_for("main.dashboard"))

from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..forms import LoginForm, RegisterForm
from ..models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Dipakai supaya login dengan email yang tidak terdaftar memakan waktu yang sama
# dengan password salah (mencegah orang menebak email mana yang terdaftar dari
# selisih waktu respons).
_DUMMY_HASH = generate_password_hash("tidak-pernah-dipakai")


def _safe_next(target: str | None) -> str | None:
    """Hanya terima path relatif di situs ini (cegah open redirect)."""
    if not target or "\\" in target or not target.startswith("/") or target.startswith("//"):
        return None
    parsed = urlparse(target)
    return target if not parsed.scheme and not parsed.netloc else None


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        taken = db.session.scalar(select(User.id).where(User.email == form.email.data))
        if taken:
            form.email.errors.append("Email ini sudah terdaftar.")
        else:
            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:  # dua pendaftaran email sama bersamaan
                db.session.rollback()
                form.email.errors.append("Email ini sudah terdaftar.")
            else:
                login_user(user)
                flash(f"Akun dibuat. Selamat datang, {user.username}.", "success")
                return redirect(url_for("main.dashboard"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(select(User).where(User.email == form.email.data))
        if user is None:
            check_password_hash(_DUMMY_HASH, form.password.data)
            valid = False
        else:
            valid = user.check_password(form.password.data)

        if valid:
            login_user(user, remember=form.remember.data)
            return redirect(_safe_next(request.args.get("next")) or url_for("main.dashboard"))
        # Satu pesan untuk dua kemungkinan salah, supaya tidak membocorkan email terdaftar.
        flash("Email atau password salah.", "error")
    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Kamu sudah keluar.", "info")
    return redirect(url_for("main.landing"))

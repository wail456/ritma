from flask import Flask, flash, make_response, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config

from .extensions import csrf, db, login_manager, migrate
from .models import CATEGORIES, CATEGORY_LABELS, User
from .services import timeutil


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    if not app.config.get("SECRET_KEY"):
        if app.config["APP_ENV"] == "production":
            raise RuntimeError("SECRET_KEY wajib diisi di production.")
        app.config["SECRET_KEY"] = "dev-only-key-jangan-dipakai-di-production"

    # Di Render, TLS diakhiri oleh proxy. ProxyFix membuat Flask tahu request aslinya
    # HTTPS (penting untuk cookie Secure dan pemeriksaan CSRF).
    if app.config["APP_ENV"] == "production":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        # Permintaan HTMX tidak boleh diarahkan ke halaman login lalu ditempel ke
        # tengah daftar habit. Suruh browser pindah halaman penuh.
        if request.headers.get("HX-Request"):
            response = make_response("", 401)
            response.headers["HX-Redirect"] = url_for("auth.login")
            return response
        flash("Masuk dulu untuk lanjut.", "info")
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))

    from .routes import auth, export, habits, main

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(habits.bp)
    app.register_blueprint(export.bp)

    # ---- template helpers ----
    app.jinja_env.filters["cat_label"] = lambda value: CATEGORY_LABELS.get(value, value)
    app.jinja_env.filters["long_date"] = timeutil.long_date
    app.jinja_env.filters["short_date"] = timeutil.short_date
    # 78.4 -> "78,4"; 100.0 -> "100" (format Indonesia: koma desimal, tanpa ",0" yang percuma)
    app.jinja_env.filters["pct"] = lambda x: f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")

    @app.context_processor
    def inject_globals():
        return {"CATEGORIES": CATEGORIES}

    # ---- error pages ----
    def _error(code: int, title: str, message: str):
        return render_template("error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(_):
        return _error(400, "Permintaan tidak valid", "Ada data yang tidak bisa diproses.")

    @app.errorhandler(CSRFError)
    def csrf_failed(_):
        return _error(400, "Sesi form kedaluwarsa", "Muat ulang halaman lalu coba lagi.")

    @app.errorhandler(404)
    def not_found(_):
        return _error(404, "Halaman tidak ditemukan", "Alamat yang kamu buka tidak ada atau bukan milikmu.")

    @app.errorhandler(409)
    def conflict(_):
        return _error(409, "Tidak bisa diproses", "Habit ini sedang diarsipkan.")

    @app.errorhandler(500)
    def server_error(_):
        db.session.rollback()
        return _error(500, "Terjadi kesalahan", "Ini salah kami, bukan kamu. Coba lagi sebentar.")

    # ---- header keamanan ----
    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        return response

    return app

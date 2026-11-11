import re
from datetime import timedelta

from app.extensions import db
from app.models import Habit, HabitLog, User
from app.services.timeutil import local_today
from tests.conftest import register


def make_habit(client, name="Minum air", category="Health"):
    return client.post("/habits/", data={"name": name, "category": category}, follow_redirects=True)


def habit_id(app, name="Minum air"):
    with app.app_context():
        return Habit.query.filter_by(name=name).one().id


def test_landing_and_health(client):
    assert client.get("/").status_code == 200
    r = client.get("/healthz")
    assert r.status_code == 200


def test_dashboard_requires_login(client):
    r = client.get("/dashboard")
    assert r.status_code == 302 and "/auth/login" in r.headers["Location"]


def test_register_login_logout(client):
    r = register(client)
    assert b"budi" in r.data
    client.post("/auth/logout")
    assert client.get("/dashboard").status_code == 302
    r = client.post("/auth/login", data={"email": "budi@example.com", "password": "password123"},
                    follow_redirects=True)
    assert b"budi" in r.data


def test_register_rejects_duplicate_and_short_password(client):
    register(client)
    client.post("/auth/logout")
    r = register(client, name="lain", email="budi@example.com")
    with client.application.app_context():
        assert User.query.count() == 1
    r = register(client, name="x", email="x@example.com", password="short")
    with client.application.app_context():
        assert User.query.count() == 1


def test_wrong_password_rejected(client):
    register(client)
    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "budi@example.com", "password": "salah-banget"})
    assert client.get("/dashboard").status_code == 302


def test_login_open_redirect_blocked(client):
    register(client)
    client.post("/auth/logout")
    r = client.post("/auth/login?next=https://evil.example",
                    data={"email": "budi@example.com", "password": "password123"})
    assert "evil.example" not in r.headers["Location"]


def test_create_habit_and_validation(user_client, app):
    make_habit(user_client)
    with app.app_context():
        assert Habit.query.count() == 1
    user_client.post("/habits/", data={"name": "", "category": "Health"})
    user_client.post("/habits/", data={"name": "x" * 81, "category": "Health"})
    user_client.post("/habits/", data={"name": "ok", "category": "Bogus"})
    with app.app_context():
        assert Habit.query.count() == 1


def test_max_active_habits(user_client, app):
    app.config["MAX_ACTIVE_HABITS"] = 2
    for i in range(4):
        make_habit(user_client, f"h{i}")
    with app.app_context():
        assert Habit.query.count() == 2


def test_toggle_semantics(user_client, app):
    make_habit(user_client)
    hid = habit_id(app)
    url = f"/habits/{hid}/log"

    def logs():
        with app.app_context():
            return [l.status for l in HabitLog.query.all()]

    user_client.post(url, data={"status": "completed"})
    assert logs() == ["completed"]
    user_client.post(url, data={"status": "completed"})      # klik lagi = batal
    assert logs() == []
    user_client.post(url, data={"status": "skipped"})
    user_client.post(url, data={"status": "completed"})      # ganti status
    assert logs() == ["completed"]


def test_bad_status_400(user_client, app):
    make_habit(user_client)
    r = user_client.post(f"/habits/{habit_id(app)}/log", data={"status": "hack"})
    assert r.status_code == 400


def test_htmx_response_has_row_and_oob(user_client, app):
    make_habit(user_client)
    r = user_client.post(f"/habits/{habit_id(app)}/log", data={"status": "completed"},
                         headers={"HX-Request": "true"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'data-status="completed"' in html
    assert html.count('hx-swap-oob="true"') == 2
    assert 'id="summary"' in html and 'id="heatmap"' in html
    assert "1<" in html or ">1</span>" in html


def test_non_htmx_redirects(user_client, app):
    make_habit(user_client)
    r = user_client.post(f"/habits/{habit_id(app)}/log", data={"status": "completed"})
    assert r.status_code == 302


def test_unique_constraint_one_log_per_day(user_client, app):
    make_habit(user_client)
    hid = habit_id(app)
    import sqlalchemy.exc as exc
    with app.app_context():
        day = local_today(app.config["APP_TZ"])
        db.session.add(HabitLog(habit_id=hid, log_date=day, status="completed"))
        db.session.commit()
        db.session.add(HabitLog(habit_id=hid, log_date=day, status="skipped"))
        try:
            db.session.commit()
            raised = False
        except exc.IntegrityError:
            db.session.rollback()
            raised = True
        assert raised


def test_other_users_habit_is_404(app):
    a = app.test_client()
    b = app.test_client()
    register(a)
    make_habit(a)
    hid = habit_id(app)
    register(b, name="siti", email="siti@example.com")
    assert b.post(f"/habits/{hid}/log", data={"status": "completed"}).status_code == 404
    assert b.get(f"/habits/{hid}/edit").status_code == 404
    assert b.post(f"/habits/{hid}/archive").status_code == 404
    assert b.post(f"/habits/{hid}/restore").status_code == 404
    with app.app_context():
        assert HabitLog.query.count() == 0
        assert db.session.get(Habit, hid).is_active


def test_edit_archive_restore(user_client, app):
    make_habit(user_client)
    hid = habit_id(app)
    user_client.post(f"/habits/{hid}/edit", data={"name": "Minum 2L", "category": "Health"})
    with app.app_context():
        assert db.session.get(Habit, hid).name == "Minum 2L"
    user_client.post(f"/habits/{hid}/archive")
    with app.app_context():
        assert not db.session.get(Habit, hid).is_active
    assert user_client.post(f"/habits/{hid}/log", data={"status": "completed"}).status_code == 409
    assert b"Minum 2L" in user_client.get("/habits/archived").data
    user_client.post(f"/habits/{hid}/restore")
    with app.app_context():
        assert db.session.get(Habit, hid).is_active


def test_dashboard_shows_streak_from_history(user_client, app):
    make_habit(user_client)
    hid = habit_id(app)
    with app.app_context():
        today = local_today(app.config["APP_TZ"])
        h = db.session.get(Habit, hid)
        h.created_at = h.created_at - timedelta(days=10)
        for i in (1, 2, 3):
            db.session.add(HabitLog(habit_id=hid, log_date=today - timedelta(days=i), status="completed"))
        db.session.commit()
    html = user_client.get("/dashboard").get_data(as_text=True)
    assert re.search(r'class="stat-value">\s*<svg.*?</svg>\s*<span>3</span>', html, re.S)


def test_export_csv_and_injection_guard(user_client, app):
    make_habit(user_client, name="=cmd|calc")
    hid = habit_id(app, "=cmd|calc")
    user_client.post(f"/habits/{hid}/log", data={"status": "completed"})
    r = user_client.get("/export/csv")
    text = r.get_data(as_text=True)
    assert r.mimetype == "text/csv"
    assert "'=cmd|calc" in text and ",=cmd" not in text
    j = user_client.get("/export/json")
    assert j.status_code == 200 and "habits" in j.get_json() or isinstance(j.get_json(), (dict, list))


def test_export_only_own_data(app):
    a, b = app.test_client(), app.test_client()
    register(a); make_habit(a, "rahasia")
    register(b, name="siti", email="siti@example.com")
    assert "rahasia" not in b.get("/export/csv").get_data(as_text=True)
    assert "rahasia" not in b.get("/export/json").get_data(as_text=True)


def test_security_headers_and_404(client):
    r = client.get("/")
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]
    assert client.get("/nggak-ada").status_code == 404


def test_habits_index_lists_only_own_and_has_export(app):
    a, b = app.test_client(), app.test_client()
    register(a); make_habit(a, "punya-budi")
    register(b, name="siti", email="siti@example.com"); make_habit(b, "punya-siti")
    html = a.get("/habits/").get_data(as_text=True)
    assert "punya-budi" in html and "punya-siti" not in html
    assert "/export/csv" in html and "/export/json" in html


def test_habits_index_requires_login(client):
    r = client.get("/habits/")
    assert r.status_code == 302 and "/auth/login" in r.headers["Location"]


def test_nav_for_logged_in_user_renders_and_logout_is_post(user_client):
    r = user_client.get("/dashboard")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'action="/auth/logout"' in html and 'method="post"' in html
    assert "X-CSRFToken" in html                      # token untuk request HTMX
    assert user_client.get("/auth/logout").status_code == 405   # logout lewat GET ditolak


def test_create_habit_still_works_via_dashboard_dialog_form(user_client, app):
    make_habit(user_client, "Dari dialog")
    assert b"Dari dialog" in user_client.get("/dashboard").data


def test_completed_cannot_be_skipped_but_can_be_reverted(user_client, app):
    make_habit(user_client)
    url = f"/habits/{habit_id(app)}/log"

    def logs():
        with app.app_context():
            return [l.status for l in HabitLog.query.all()]

    user_client.post(url, data={"status": "completed"})
    user_client.post(url, data={"status": "skipped"})      # diabaikan
    assert logs() == ["completed"]
    user_client.post(url, data={"status": "completed"})    # batal lewat centang
    assert logs() == []
    user_client.post(url, data={"status": "skipped"})
    user_client.post(url, data={"status": "completed"})    # skipped -> completed boleh
    assert logs() == ["completed"]


def test_skip_button_disabled_in_html_when_completed(user_client, app):
    make_habit(user_client)
    url = f"/habits/{habit_id(app)}/log"
    html = user_client.post(url, data={"status": "completed"}, headers={"HX-Request": "true"}).get_data(as_text=True)
    assert re.search(r'<button class="skip"[^>]*\bdisabled\b', html)
    html = user_client.post(url, data={"status": "completed"}, headers={"HX-Request": "true"}).get_data(as_text=True)
    assert not re.search(r'<button class="skip"[^>]*\bdisabled\b', html)   # sudah dibatalkan


def test_confirm_dialog_present_and_no_window_confirm(user_client):
    html = user_client.get("/dashboard").get_data(as_text=True)
    assert 'id="confirm-dialog"' in html
    js = user_client.get("/static/js/app.js").get_data(as_text=True)
    assert "window.confirm" not in js

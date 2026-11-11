"""Isi akun demo dengan riwayat 90 hari yang deterministik.

Pakai:  python seed.py           (aman dijalankan berulang; akun demo dibuat ulang)
Login:  demo@example.com / password123
"""
import random
from datetime import datetime, time, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import Habit, HabitLog, User
from app.services.timeutil import local_today

DEMO_EMAIL = "demo@example.com"
DAYS = 90
OFF_DAYS = {2, 3, 9, 17, 18, 31, 44}

# (nama, kategori, deskripsi, peluang selesai, hari sejak mulai)
HABITS = [
    ("Minum 2 liter air", "Health", "Satu botol sebelum makan siang", 0.85, 90),
    ("Jalan kaki 20 menit", "Health", "", 0.65, 90),
    ("Baca 15 halaman", "Learning", "Buku apa saja", 0.7, 75),
    ("Latihan soal algoritma", "Learning", "Satu soal per hari", 0.55, 60),
    ("Rapikan to-do besok", "Productivity", "Sebelum tidur", 0.75, 45),
    ("Tidur sebelum jam 11", "Health", "", 0.5, 30),
]


def seed():
    app = create_app()
    with app.app_context():
        old = User.query.filter_by(email=DEMO_EMAIL).first()
        if old:
            db.session.delete(old)
            db.session.commit()

        user = User(username="demo", email=DEMO_EMAIL)
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        today = local_today(app.config["APP_TZ"])
        rng = random.Random(42)
        for name, cat, desc, p, age in HABITS:
            start = today - timedelta(days=age)
            habit = Habit(user_id=user.id, name=name, category=cat, description=desc,
                          created_at=datetime.combine(start, time(8, 0), tzinfo=timezone.utc))
            db.session.add(habit)
            db.session.flush()
            for i in range(age, 0, -1):          # sampai kemarin; hari ini sengaja kosong
                day = today - timedelta(days=i)
                r = rng.random()
                if i in OFF_DAYS:        # hari bolong supaya streak tidak mulus 90 hari
                    continue
                if r < p:
                    db.session.add(HabitLog(habit_id=habit.id, log_date=day, status="completed"))
                elif r < p + 0.05:
                    db.session.add(HabitLog(habit_id=habit.id, log_date=day, status="skipped"))
        db.session.commit()
        print(f"Selesai. Login: {DEMO_EMAIL} / password123")


if __name__ == "__main__":
    seed()

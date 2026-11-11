from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

COMPLETED = "completed"
SKIPPED = "skipped"
STATUSES = (COMPLETED, SKIPPED)  # "pending" = tidak ada baris log sama sekali

# (nilai di database, label di UI)
CATEGORIES = (
    ("General", "Umum"),
    ("Health", "Kesehatan"),
    ("Productivity", "Produktivitas"),
    ("Learning", "Belajar"),
)
CATEGORY_LABELS = dict(CATEGORIES)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    habits = db.relationship(
        "Habit", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Habit(db.Model):
    __tablename__ = "habits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(40), nullable=False, default="General")
    # False = diarsipkan (soft delete). Riwayat log tetap ada dan ikut terekspor.
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="habits")
    logs = db.relationship(
        "HabitLog", back_populates="habit", cascade="all, delete-orphan"
    )

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)


class HabitLog(db.Model):
    __tablename__ = "habit_logs"
    __table_args__ = (
        # Satu habit hanya boleh punya satu catatan per tanggal. Dijaga di level
        # database, jadi dua request bersamaan tidak bisa membuat duplikat.
        UniqueConstraint("habit_id", "log_date", name="uq_habit_log_per_day"),
        CheckConstraint("status IN ('completed', 'skipped')", name="ck_habit_log_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(
        db.Integer, db.ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    log_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    habit = db.relationship("Habit", back_populates="logs")

"""Lapisan yang menghubungkan database dengan logika murni di stats.py."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import COMPLETED, SKIPPED, Habit, HabitLog
from . import stats, timeutil


@dataclass
class Summary:
    active: int
    done_today: int
    total_today: int
    current_streak: int
    best_streak: int
    rate_30: float

    @property
    def progress_percent(self) -> int:
        return round(self.done_today / self.total_today * 100) if self.total_today else 0


@dataclass
class DashboardData:
    today: date
    habits: list[Habit]
    today_status: dict[int, str]  # habit_id -> 'completed' | 'skipped' (tidak ada = pending)
    summary: Summary
    heatmap: stats.Heatmap
    categories: list[str]


def build_dashboard(user_id: int, today: date | None = None) -> DashboardData:
    tz = current_app.config["APP_TZ"]
    mode = current_app.config["STREAK_MODE"]
    today = today or timeutil.local_today(tz)

    habits = list(
        db.session.scalars(
            select(Habit)
            .where(Habit.user_id == user_id, Habit.is_active.is_(True))
            .order_by(Habit.created_at, Habit.id)
        )
    )

    today_status: dict[int, str] = {}
    completed: list[tuple[int, date]] = []
    if habits:
        rows = db.session.execute(
            select(HabitLog.habit_id, HabitLog.log_date, HabitLog.status).where(
                HabitLog.habit_id.in_([h.id for h in habits])
            )
        )
        for habit_id, log_date, status in rows:
            if status == COMPLETED:
                completed.append((habit_id, log_date))
            if log_date == today:
                today_status[habit_id] = status

    starts = {h.id: timeutil.to_local_date(h.created_at, tz) for h in habits}
    first_day = min(starts.values(), default=today)
    daily = stats.build_daily(starts, completed, first_day, today)

    todays = daily.get(today, stats.DayStat(0, 0))
    window_start = max(first_day, today - timedelta(days=29))  # 30 hari terakhir
    summary = Summary(
        active=len(habits),
        done_today=todays.done,
        total_today=todays.total,
        current_streak=stats.current_streak(daily, today, mode),
        best_streak=stats.best_streak(daily, mode),
        rate_30=stats.completion_rate(daily, window_start, today),
    )

    categories = sorted({h.category for h in habits})
    return DashboardData(
        today=today,
        habits=habits,
        today_status=today_status,
        summary=summary,
        heatmap=stats.heatmap_weeks(daily, today),
        categories=categories,
    )


def set_log(habit: Habit, day: date, status: str) -> str | None:
    """Toggle status log. Mengembalikan status baru, atau None kalau kembali ke pending.

        belum ada log          -> buat log dengan status ini
        log ada, status sama   -> hapus log (kembali pending)   <- inilah "toggle"
        log completed, minta skipped -> diabaikan (batalkan dulu dengan klik centang lagi)
        log skipped, status apa pun  -> diabaikan: "Lewati" bersifat final untuk hari itu

    Dua klik hampir bersamaan bisa sama-sama melihat "belum ada log" lalu sama-sama
    INSERT. Constraint UNIQUE(habit_id, log_date) menolak yang kedua; kita tangkap
    IntegrityError itu dan ulangi sekali, kali ini log-nya sudah ada.
    """
    for attempt in (1, 2):
        log = db.session.scalar(
            select(HabitLog).where(HabitLog.habit_id == habit.id, HabitLog.log_date == day)
        )
        if log is None:
            db.session.add(HabitLog(habit_id=habit.id, log_date=day, status=status))
            result: str | None = status
        elif log.status == SKIPPED:
            return SKIPPED  # final; sama dengan tombol yang nonaktif di UI
        elif log.status == status:
            db.session.delete(log)  # completed + centang lagi = batal
            result = None
        elif log.status == COMPLETED and status == SKIPPED:
            return COMPLETED  # selesai tidak bisa "dilewati"
        else:
            log.status = status
            result = status
        try:
            db.session.commit()
            return result
        except IntegrityError:
            db.session.rollback()
            if attempt == 2:
                raise
    return None  # tidak tercapai; menenangkan type checker
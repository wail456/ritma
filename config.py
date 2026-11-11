"""Konfigurasi aplikasi. Semua nilai sensitif dibaca dari environment variable."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _database_uri() -> str:
    """Pilih database: SQLite untuk development, PostgreSQL (Neon) untuk production.

    - Tanpa DATABASE_URL  -> file SQLite di folder instance/ (relatif ke instance_path
      Flask-SQLAlchemy 3, jadi jangan tulis 'instance/' lagi di depannya).
    - Provider cloud sering memberi 'postgres://' atau 'postgresql://'. Keduanya
      diubah ke 'postgresql+psycopg://' supaya SQLAlchemy memakai driver psycopg v3
      (cara yang direkomendasikan Neon).
    """
    url = os.environ.get("DATABASE_URL", "sqlite:///habit_tracker.db")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


APP_ENV = os.environ.get("APP_ENV", "development")  # "production" di Render


class Config:
    APP_ENV = APP_ENV
    # Tidak ada fallback key di sini. create_app() menolak start di production
    # kalau SECRET_KEY kosong (fallback tertulis di repo = siapa pun bisa memalsukan sesi).
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _database_uri()

    # Neon mematikan compute yang idle (scale to zero). Koneksi lama jadi basi,
    # jadi cek dulu sebelum dipakai dan daur ulang sebelum 5 menit.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = APP_ENV == "production"

    # Server (Render) berjalan di UTC, pengguna di WIB. "Hari ini" harus dihitung
    # di zona waktu pengguna, kalau tidak, jam 00:00-07:00 WIB masih dianggap kemarin.
    APP_TZ = os.environ.get("APP_TZ", "Asia/Jakarta")

    # "any": hari dihitung streak kalau minimal 1 habit selesai.
    # "all": hari dihitung streak kalau semua habit aktif selesai.
    STREAK_MODE = os.environ.get("STREAK_MODE", "any")

    MAX_ACTIVE_HABITS = 25

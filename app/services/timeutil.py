"""Semua konversi dan format waktu ada di sini supaya aturan zona waktunya hanya satu tempat."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
BULAN_PENDEK = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
BULAN_PANJANG = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)


def local_today(tz_name: str) -> date:
    """Tanggal hari ini menurut zona waktu pengguna (bukan zona waktu server)."""
    return datetime.now(ZoneInfo(tz_name)).date()


def to_local_date(dt: datetime, tz_name: str) -> date:
    """Ubah timestamp database jadi tanggal lokal.

    SQLite mengembalikan datetime tanpa info zona; isinya selalu UTC karena
    kita menyimpannya begitu. PostgreSQL mengembalikan datetime ber-zona.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(tz_name)).date()


def greeting(tz_name: str) -> str:
    """Sapaan menurut jam di zona waktu pengguna."""
    hour = datetime.now(ZoneInfo(tz_name)).hour
    if 4 <= hour < 11:
        return "Selamat pagi"
    if 11 <= hour < 15:
        return "Selamat siang"
    if 15 <= hour < 18:
        return "Selamat sore"
    return "Selamat malam"


def long_date(d: date) -> str:
    """'Senin, 9 November 2026'"""
    return f"{HARI[d.weekday()]}, {d.day} {BULAN_PANJANG[d.month - 1]} {d.year}"


def short_date(d: date) -> str:
    """'9 Nov 2026'"""
    return f"{d.day} {BULAN_PENDEK[d.month - 1]} {d.year}"

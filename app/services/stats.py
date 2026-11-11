"""Logika bisnis murni: streak, completion rate, heatmap.

File ini sengaja TIDAK mengimpor Flask atau database. Isinya fungsi biasa yang
menerima data biasa, jadi bisa dibaca, dites, dan dinilai tanpa menjalankan server.

Semua angka di dashboard berasal dari satu struktur:

    daily = {tanggal: DayStat(done, total)}

    done  = berapa habit yang diselesaikan pada tanggal itu
    total = berapa habit yang "berlaku" pada tanggal itu, yaitu habit aktif
            yang sudah dibuat pada atau sebelum tanggal itu

Streak, completion rate, dan warna heatmap hanya membaca `daily`. Karena satu
sumber, ketiganya tidak mungkin saling bertentangan.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Mapping

BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
STREAK_MODES = ("any", "all")
ONE_DAY = timedelta(days=1)


@dataclass(frozen=True)
class DayStat:
    done: int
    total: int

    @property
    def ratio(self) -> float:
        return self.done / self.total if self.total else 0.0


# --------------------------------------------------------------------------
# 1. Membangun data harian
# --------------------------------------------------------------------------
def build_daily(
    habit_starts: Mapping[int, date],
    completed_logs: Iterable[tuple[int, date]],
    start: date,
    end: date,
) -> dict[date, DayStat]:
    """Bangun DayStat untuk setiap tanggal dari `start` sampai `end` (inklusif).

    habit_starts   : {habit_id: tanggal habit mulai berlaku}, hanya habit AKTIF.
    completed_logs : pasangan (habit_id, tanggal) untuk log berstatus 'completed'.

    Dua aturan yang menjaga angka tetap jujur:
    - Habit baru tidak dihukum untuk hari sebelum dia dibuat. Habit yang dibuat
      3 hari lalu hanya punya 3 kesempatan, bukan 30.
    - Log di luar kemungkinan (sebelum habit dibuat, setelah `end`, habit tidak
      aktif) diabaikan. Akibatnya done <= total selalu terpenuhi.
    """
    starts_sorted = sorted(habit_starts.values())
    done: Counter[date] = Counter()
    for habit_id, day in completed_logs:
        habit_start = habit_starts.get(habit_id)
        if habit_start is None or day < habit_start:
            continue
        if start <= day <= end:
            done[day] += 1

    daily: dict[date, DayStat] = {}
    day = start
    while day <= end:
        total = bisect_right(starts_sorted, day)  # jumlah habit dengan start <= day
        daily[day] = DayStat(done=done[day], total=total)
        day += ONE_DAY
    return daily


# --------------------------------------------------------------------------
# 2. Streak
# --------------------------------------------------------------------------
def day_counts(stat: DayStat | None, mode: str = "any") -> bool:
    """Apakah hari ini dihitung sebagai bagian dari streak?"""
    if mode not in STREAK_MODES:
        raise ValueError(f"mode streak harus salah satu dari {STREAK_MODES}")
    if stat is None or stat.total == 0:
        return False
    if mode == "all":
        return stat.done >= stat.total
    return stat.done >= 1


def current_streak(daily: Mapping[date, DayStat], today: date, mode: str = "any") -> int:
    """Jumlah hari berturut-turut yang dihitung, mundur dari hari ini.

    Kalau hari ini belum memenuhi syarat, hitungan dimulai dari kemarin. Tanpa
    aturan ini streak akan putus setiap pagi sebelum pengguna sempat mencentang.
    """
    day = today
    if not day_counts(daily.get(day), mode):
        day -= ONE_DAY
    streak = 0
    while day_counts(daily.get(day), mode):
        streak += 1
        day -= ONE_DAY
    return streak


def best_streak(daily: Mapping[date, DayStat], mode: str = "any") -> int:
    """Rangkaian hari berturut-turut terpanjang sepanjang riwayat."""
    best = run = 0
    prev: date | None = None
    for day in sorted(daily):
        if not day_counts(daily[day], mode):
            run, prev = 0, None
            continue
        run = run + 1 if prev is not None and (day - prev).days == 1 else 1
        prev = day
        best = max(best, run)
    return best


# --------------------------------------------------------------------------
# 3. Completion rate
# --------------------------------------------------------------------------
def completion_rate(daily: Mapping[date, DayStat], start: date, end: date) -> float:
    """Persentase penyelesaian pada rentang [start, end].

        rate = jumlah habit selesai / jumlah kesempatan * 100

    "Kesempatan" dijumlahkan per hari (DayStat.total), bukan dihitung sebagai
    habit_aktif * jumlah_hari. Selisihnya muncul saat ada habit yang dibuat di
    tengah rentang: rumus kasar menganggap habit itu sudah ada sejak hari
    pertama sehingga persentasenya terseret turun.

    Total kesempatan 0 mengembalikan 0.0 (mencegah pembagian dengan nol).
    """
    done = total = 0
    day = start
    while day <= end:
        stat = daily.get(day)
        if stat is not None:
            done += stat.done
            total += stat.total
        day += ONE_DAY
    return round(done / total * 100, 1) if total else 0.0


# --------------------------------------------------------------------------
# 4. Heatmap
# --------------------------------------------------------------------------
def heat_level(stat: DayStat | None) -> int:
    """Level warna 0-3 dari persentase penyelesaian (dibulatkan ke atas pada .5).

        0       -> 0% atau tidak ada habit
        1-33%   -> level 1
        34-66%  -> level 2
        67-100% -> level 3
    """
    if stat is None or stat.total == 0 or stat.done == 0:
        return 0
    percent = int(stat.ratio * 100 + 0.5)
    if percent <= 33:
        return 1
    if percent <= 66:
        return 2
    return 3


@dataclass(frozen=True)
class Cell:
    day: date
    done: int
    total: int
    level: int
    future: bool  # tanggal setelah hari ini (hanya pengisi grid)
    is_today: bool

    @property
    def empty(self) -> bool:
        """Belum ada habit aktif pada hari itu (bukan sama dengan 0%)."""
        return self.total == 0 and not self.future


@dataclass(frozen=True)
class Heatmap:
    weeks: list[list[Cell]]  # tiap elemen = satu kolom (Senin..Minggu)
    month_labels: list[str]  # sepanjang weeks; "" jika tidak ada label


def heatmap_weeks(daily: Mapping[date, DayStat], today: date, weeks: int = 53) -> Heatmap:
    """Grid ala GitHub: `weeks` kolom, 7 baris (Senin..Minggu), kolom terakhir
    memuat hari ini. Sel setelah hari ini ditandai `future`."""
    this_monday = today - timedelta(days=today.weekday())
    first_monday = this_monday - timedelta(weeks=weeks - 1)

    columns: list[list[Cell]] = []
    for w in range(weeks):
        column = []
        for i in range(7):
            day = first_monday + timedelta(weeks=w, days=i)
            stat = daily.get(day)
            column.append(
                Cell(
                    day=day,
                    done=stat.done if stat else 0,
                    total=stat.total if stat else 0,
                    level=heat_level(stat),
                    future=day > today,
                    is_today=day == today,
                )
            )
        columns.append(column)

    # Label bulan: di kolom tempat bulan Senin-nya berganti. Label kolom pertama
    # dibuang kalau label berikutnya terlalu dekat (akan bertumpuk).
    starts = [
        i for i, col in enumerate(columns)
        if i == 0 or col[0].day.month != columns[i - 1][0].day.month
    ]
    if len(starts) > 1 and starts[1] - starts[0] < 3:
        starts.pop(0)
    labels = [""] * len(columns)
    for i in starts:
        labels[i] = BULAN[columns[i][0].day.month - 1]
    return Heatmap(weeks=columns, month_labels=labels)

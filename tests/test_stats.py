"""Tes logika murni (tanpa database). Tiap tes menjelaskan satu aturan bisnis."""
import random
from datetime import date, timedelta

import pytest

from app.services import stats
from app.services.stats import DayStat

TODAY = date(2026, 11, 9)  # hari Senin


def d(n: int) -> date:
    """Tanggal n hari sebelum TODAY."""
    return TODAY - timedelta(days=n)


def make_daily(counted_days: set[int], total: int = 1, span: int = 20) -> dict:
    """daily dengan `total` habit tiap hari; hari yang ada di counted_days (n hari lalu) semuanya selesai."""
    return {d(n): DayStat(done=total if n in counted_days else 0, total=total) for n in range(span)}


# ---------------------------------------------------------------- build_daily
def test_habit_baru_tidak_dihukum_untuk_hari_sebelum_dibuat():
    starts = {1: date(2026, 11, 1), 2: date(2026, 11, 7)}
    daily = stats.build_daily(starts, [], date(2026, 11, 1), TODAY)
    assert daily[date(2026, 11, 6)].total == 1  # baru habit 1
    assert daily[date(2026, 11, 7)].total == 2  # habit 2 mulai berlaku
    assert daily[TODAY].total == 2


def test_log_yang_mustahil_diabaikan():
    starts = {1: date(2026, 11, 5)}
    logs = [
        (1, date(2026, 11, 3)),   # sebelum habit dibuat
        (99, date(2026, 11, 6)),  # habit tidak aktif / bukan milik user
        (1, date(2026, 11, 20)),  # di masa depan
        (1, date(2026, 11, 6)),   # satu-satunya yang sah
    ]
    daily = stats.build_daily(starts, logs, date(2026, 11, 1), TODAY)
    assert sum(s.done for s in daily.values()) == 1
    assert daily[date(2026, 11, 6)].done == 1


def test_done_tidak_pernah_melebihi_total():
    rng = random.Random(7)
    starts = {i: TODAY - timedelta(days=rng.randint(0, 60)) for i in range(1, 8)}
    logs = [(h, TODAY - timedelta(days=n)) for h in starts for n in range(70) if rng.random() < 0.6]
    daily = stats.build_daily(starts, logs, TODAY - timedelta(days=60), TODAY)
    assert all(0 <= s.done <= s.total for s in daily.values())


# ------------------------------------------------------------ completion rate
def test_completion_rate_lebih_adil_daripada_rumus_kasar():
    # Habit A dibuat 9 hari lalu, habit B baru 3 hari lalu. Keduanya selesai setiap
    # hari sejak dibuat. Itu sempurna, jadi hasil yang benar adalah 100%.
    starts = {1: date(2026, 11, 1), 2: date(2026, 11, 7)}
    logs = [(1, date(2026, 11, n)) for n in range(1, 10)] + [(2, date(2026, 11, n)) for n in range(7, 10)]
    daily = stats.build_daily(starts, logs, date(2026, 11, 1), TODAY)

    assert stats.completion_rate(daily, date(2026, 11, 1), TODAY) == 100.0

    # Rumus kasar blueprint: selesai / (habit_aktif x jumlah_hari) menganggap B sudah ada
    # sejak hari pertama, jadi hasilnya terseret turun padahal tidak ada hari yang terlewat.
    naive = round(12 / (2 * 9) * 100, 1)
    assert naive == 66.7


def test_completion_rate_tanpa_kesempatan_adalah_nol_bukan_error():
    assert stats.completion_rate({}, date(2026, 11, 1), TODAY) == 0.0
    kosong = {TODAY: DayStat(0, 0)}
    assert stats.completion_rate(kosong, TODAY, TODAY) == 0.0


def test_completion_rate_pembulatan_satu_desimal():
    daily = {TODAY: DayStat(1, 3)}
    assert stats.completion_rate(daily, TODAY, TODAY) == 33.3


# --------------------------------------------------------------------- streak
def test_streak_hari_ini_belum_diisi_tidak_memutus():
    daily = make_daily({1, 2, 3, 4})  # kemarin dan 3 hari sebelumnya; hari ini kosong
    assert stats.current_streak(daily, TODAY) == 4


def test_streak_hari_ini_ikut_dihitung_kalau_sudah_diisi():
    daily = make_daily({0, 1, 2, 3, 4})
    assert stats.current_streak(daily, TODAY) == 5


def test_streak_putus_kalau_ada_hari_kosong():
    daily = make_daily({0, 1, 3, 4, 5})  # lubang di 2 hari lalu
    assert stats.current_streak(daily, TODAY) == 2


def test_streak_nol_kalau_kemarin_dan_hari_ini_kosong():
    daily = make_daily({2, 3, 4})
    assert stats.current_streak(daily, TODAY) == 0


def test_streak_tanpa_data():
    assert stats.current_streak({}, TODAY) == 0
    assert stats.best_streak({}) == 0


def test_best_streak_mengambil_rangkaian_terpanjang():
    daily = make_daily({0, 1, 5, 6, 7, 8, 9, 12})
    assert stats.best_streak(daily) == 5
    assert stats.current_streak(daily, TODAY) == 2


def test_best_streak_tidak_menyambung_lintas_lubang_data():
    # Dua hari bersebelahan di dict tapi tanggalnya terpaut, jangan dianggap berurutan.
    daily = {d(10): DayStat(1, 1), d(5): DayStat(1, 1)}
    assert stats.best_streak(daily) == 1


def test_mode_all_butuh_semua_habit_selesai():
    daily = {
        d(2): DayStat(3, 3),
        d(1): DayStat(2, 3),  # satu habit terlewat
        d(0): DayStat(3, 3),
    }
    assert stats.current_streak(daily, TODAY, mode="any") == 3
    assert stats.current_streak(daily, TODAY, mode="all") == 1
    assert stats.best_streak(daily, mode="all") == 1


def test_hari_tanpa_habit_tidak_dihitung():
    daily = {d(1): DayStat(0, 0), d(0): DayStat(1, 1)}
    assert stats.current_streak(daily, TODAY) == 1


def test_mode_streak_tidak_dikenal_ditolak():
    with pytest.raises(ValueError):
        stats.current_streak({TODAY: DayStat(1, 1)}, TODAY, mode="sembarang")


# -------------------------------------------------------------------- heatmap
@pytest.mark.parametrize(
    "done,total,level",
    [
        (0, 5, 0),   # 0%
        (0, 0, 0),   # tidak ada habit
        (1, 4, 1),   # 25%
        (1, 3, 1),   # 33%
        (3, 8, 2),   # 37,5% -> 38%
        (1, 2, 2),   # 50%
        (2, 3, 3),   # 66,7% -> 67%
        (3, 4, 3),   # 75%
        (5, 5, 3),   # 100%
    ],
)
def test_level_heatmap_mengikuti_ambang_blueprint(done, total, level):
    assert stats.heat_level(DayStat(done, total)) == level


def test_heatmap_bentuk_dan_isi_grid():
    daily = {TODAY - timedelta(days=n): DayStat(1, 2) for n in range(0, 400)}
    hm = stats.heatmap_weeks(daily, TODAY, weeks=53)

    assert len(hm.weeks) == 53 and all(len(col) == 7 for col in hm.weeks)
    assert len(hm.month_labels) == 53
    assert all(col[0].day.weekday() == 0 for col in hm.weeks)  # tiap kolom mulai Senin

    last = hm.weeks[-1]
    assert [c.is_today for c in last].count(True) == 1
    assert last[0].day == TODAY  # 9 Nov 2026 memang hari Senin
    assert all(c.future for c in last[1:])  # sisa minggu ini belum terjadi
    assert not any(c.future for col in hm.weeks[:-1] for c in col)


def test_heatmap_sel_sebelum_ada_habit_ditandai_kosong():
    daily = {TODAY: DayStat(1, 1)}
    hm = stats.heatmap_weeks(daily, TODAY)
    assert hm.weeks[0][0].empty  # setahun lalu belum ada habit
    assert not hm.weeks[-1][0].empty


def test_label_bulan_tidak_bertumpuk():
    for offset in range(0, 40):  # geser "hari ini" untuk menguji berbagai posisi bulan
        today = TODAY + timedelta(days=offset)
        hm = stats.heatmap_weeks({}, today)
        idx = [i for i, lab in enumerate(hm.month_labels) if lab]
        assert all(b - a >= 3 for a, b in zip(idx, idx[1:])), (today, idx)
        assert idx, "minimal satu label bulan"

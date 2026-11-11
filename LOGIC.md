# Logika Ritma

Semua hitungan ada di satu file murni (tanpa database): `app/services/stats.py`.
28 tes di `tests/test_stats.py` menguji aturan di bawah.

## 1. Satu sumber angka: `daily`
`build_daily` membuat `{tanggal: (selesai, total)}`. Streak, persentase, dan heatmap
semuanya membaca dari sini, jadi angkanya tidak bisa saling bertentangan.
Sebuah habit hanya dihitung **mulai tanggal dibuat**. Habit yang baru dibuat hari ini
tidak membuat 30 hari ke belakang terlihat "gagal".

## 2. Persentase penyelesaian 30 hari
`jumlah selesai / jumlah kesempatan`, kesempatan = habit yang sudah ada di hari itu.
Rumus naif `selesai / (jumlah habit x 30)` salah kalau habit dibuat di tengah periode.
Contoh di tes: 2 habit, yang kedua baru dibuat 1 hari lalu, semuanya selesai ->
rumus kita 100,0%, rumus naif 66,7%.
"Lewati" dihitung sebagai tidak selesai (sengaja, supaya skip tidak bisa dipakai curang).

## 3. Streak
Hari dihitung "aktif" bila minimal 1 habit selesai (mode `any`, default; mode `all`
mewajibkan semua habit, diatur lewat `STREAK_MODE`).
- Streak saat ini mundur dari hari ini. Kalau hari ini belum ada yang selesai,
  mulai dari **kemarin**: hari yang belum selesai tidak memutus streak, baru putus
  kalau kemarin juga kosong.
- Streak terbaik: urutan hari aktif berturut-turut terpanjang. Hari tanpa habit
  sama sekali (belum ada kesempatan) bukan hari aktif.

## 4. Heatmap
53 minggu x 7 hari, Senin di atas. Level warna dari persentase hari itu:
0 = nol, 1 = sampai 33%, 2 = sampai 66%, 3 = di atas 66% (pembulatan ke atas dari .5).
Di CSS, level 1-3 dipetakan ke tiga warna hijau Ritma (level 2-4 di palet), jadi tiap tingkat terlihat jelas bedanya.
Sel masa depan transparan, sel sebelum ada habit hanya garis tipis.

## 5. Master habit vs catatan harian (dua tabel berbeda)
- **`habits` = master / templat.** Satu baris per kebiasaan ("Minum 2 liter air"): nama, kategori,
  tanggal dibuat, `is_active`. Ini tidak berubah tiap hari.
- **`habit_logs` = catatan harian.** Satu baris hanya kalau habit itu sudah dicentang atau dilewati
  pada tanggal tertentu: `(habit_id, log_date, status)`. Tidak ada baris = hari itu masih "belum".
- Checklist hari ini dibuat dengan menggabungkan keduanya: semua habit aktif + log bertanggal hari ini.

**Soal "reset pukul 00:00":** tidak ada proses terjadwal (cron) yang menghapus atau mereset apa pun.
Hari baru otomatis tampil kosong karena belum ada log bertanggal hari itu, sedangkan log kemarin
tetap utuh di database. Batas "pukul 00:00" ditentukan `APP_TZ` (Asia/Jakarta), lihat bagian 6.

## 5a. Aturan centang dan membatalkan (revert)
`set_log` hanya dipanggil untuk **hari ini**; hari-hari lalu tidak bisa diubah lewat UI.
Selama hari berjalan status bebas dikoreksi supaya salah klik tidak permanen:

| Kondisi sekarang | Yang diklik | Hasil |
|---|---|---|
| belum ada log | Centang / Lewati | log dibuat dengan status itu |
| completed | Centang lagi | log dihapus (batal, kembali "belum") |
| skipped | Lewati lagi | log dihapus (batal) |
| skipped | Centang | berubah jadi completed |
| completed | Lewati | **diabaikan**: tombol Lewati nonaktif (abu-abu) dan server menolak juga |

Alasan baris terakhir: "selesai" lalu "dilewati" tanpa dibatalkan dulu membuat status yang
membingungkan. Aturannya sengaja dibuat di server, bukan hanya di tombol, supaya tidak bisa
ditembus dengan mengirim request manual.

Database menjamin satu log per habit per hari lewat `UNIQUE(habit_id, log_date)`. Kalau dua klik
beradu dan kena IntegrityError, `set_log` mengulang sekali.

## 6. Zona waktu
Server jalan di UTC, "hari ini" dihitung dengan `APP_TZ` (Asia/Jakarta). Tanpa ini,
jam 00.00-07.00 WIB akan tercatat sebagai kemarin.

## 7. Keamanan akses
Setiap habit dicek pemiliknya; milik orang lain dijawab 404 (bukan 403) agar ID
tidak bisa ditebak keberadaannya. Password di-hash, CSRF aktif (termasuk HTMX),
redirect `next` hanya path internal, ekspor CSV mengamankan sel berawalan `= + - @`.

## Trade-off yang sengaja diambil
- Mengaktifkan kembali habit yang diarsipkan menambah lagi kesempatan di hari-hari
  setelah dibuat, sehingga persentase lama bisa turun sedikit.
- Streak mode `any` lebih ramah; kalau mau ketat, set `STREAK_MODE=all`.

## Perbaikan teknis dan UI (revisi terakhir)
1. **Tombol "Lewati"**: nonaktif dan abu-abu saat habit sudah selesai (lihat tabel di 5a).
2. **Modal "Habit Baru" tidak di tengah**: penyebabnya reset CSS `* { margin: 0 }` menghapus
   `margin: auto` bawaan `<dialog>`. Diperbaiki dengan `position: fixed; inset: 0; margin: auto`.
   Hasilnya tepat di tengah (selisih 0 px dari pusat layar di desktop dan HP pada tes browser).
3. **Konfirmasi arsip**: kotak `confirm()` bawaan browser diganti dialog bertema Ritma. Form ditahan
   dulu dan baru dikirim kalau user menekan "Arsipkan"; Batal atau Esc menutupnya tanpa efek.
4. **Dashboard 2 kolom** di layar >= 1000px: daftar habit di kiri, empat kartu ringkasan di kanan
   (menempel saat scroll), heatmap lebar penuh di bawah. Di bawah 1000px kembali 1 kolom.

## Halaman Kebiasaan Saya
`GET /habits/` menampilkan semua habit aktif milik user yang login (urut dari yang paling lama),
dengan tombol Ubah, Arsipkan, dan ekspor CSV/JSON. Query-nya selalu difilter `user_id`.

## Glosarium: istilah yang mungkin baru
- **Flask**: framework Python untuk membuat web (setara Laravel di PHP, tapi jauh lebih kecil).
- **Blueprint**: cara Flask memecah route ke beberapa file (`auth`, `habits`, `export`, `main`) supaya rapi.
- **ORM / SQLAlchemy**: kamu menulis `Habit.query...` di Python, SQLAlchemy yang menerjemahkan jadi SQL. Setara Eloquent di Laravel.
- **Migrasi (Alembic / Flask-Migrate)**: file yang mencatat perubahan struktur tabel. `flask db upgrade` membuat tabel di database baru, sama seperti `php artisan migrate`.
- **Constraint UNIQUE**: aturan di database, bukan di kode, bahwa kombinasi `(habit_id, log_date)` tidak boleh ada dua kali. Ini jaring pengaman kalau dua klik beradu.
- **Soft delete (`is_active`)**: "hapus" cuma menandai habit nonaktif, datanya tetap ada supaya riwayat dan ekspor tidak hilang.
- **Hash password**: password tidak disimpan asli, hanya hasil acaknya. Saat login, password yang diketik di-hash lalu dibandingkan. Kalau database bocor, password asli tidak ikut terbaca.
- **Session & cookie**: setelah login, server memberi cookie bertanda tangan (pakai `SECRET_KEY`) supaya tahu kamu siapa di request berikutnya. Itu sebabnya `SECRET_KEY` wajib rahasia.
- **CSRF**: serangan di mana situs lain menyuruh browsermu mengirim request ke web ini diam-diam. Pertahanannya: tiap form membawa token rahasia yang harus cocok. Untuk request HTMX, token dikirim lewat header `X-CSRFToken`.
- **CSP (Content-Security-Policy)**: header yang menyuruh browser hanya menjalankan script dari domain sendiri. Karena itu tidak ada `<script>` inline di template.
- **HTMX**: library kecil yang membuat tombol bisa mengirim request lalu mengganti sebagian halaman dengan HTML dari server, tanpa menulis JavaScript sendiri. Dipakai untuk centang tanpa reload.
- **OOB swap (`hx-swap-oob`)**: satu respons HTMX bisa mengganti beberapa bagian halaman sekaligus. Satu centang mengganti baris, kartu ringkasan, dan heatmap sekaligus.
- **Progressive enhancement**: tombol centang adalah form biasa yang tetap jalan tanpa JavaScript; HTMX hanya membuatnya lebih mulus.
- **Gunicorn / WSGI**: server produksi untuk aplikasi Flask. `flask run` hanya untuk percobaan lokal.
- **Connection pool & `pool_pre_ping`**: koneksi database dipakai ulang. Neon menidurkan database saat idle, jadi koneksi dicek dulu sebelum dipakai supaya tidak error.
- **ProxyFix**: di Render, request masuk lewat proxy. ProxyFix membuat Flask tahu aslinya HTTPS, supaya cookie aman dan URL benar.
- **Environment variable**: pengaturan rahasia (`SECRET_KEY`, `DATABASE_URL`) yang disimpan di server, bukan di kode, supaya tidak ikut ter-push ke GitHub.
- **`<dialog>` / modal**: elemen HTML bawaan untuk jendela pop-up. `showModal()` menampilkannya di atas halaman dengan latar gelap, dan tombol Esc menutupnya.
- **Seed**: skrip yang mengisi data contoh (`seed.py`) supaya demo tidak kosong.
